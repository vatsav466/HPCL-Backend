using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using RabbitMQ.Client;
using TitaniumAS.Opc.Client;
using TitaniumAS.Opc.Client.Da;
using TitaniumAS.Opc.Client.Common;
using TitaniumAS.Opc.Client.Da.Browsing;
using System.Linq;
using System.Diagnostics;
using System.Data.Odbc;
using System.Threading.Channels;
using System.Runtime.Remoting.Channels;

namespace OpcdaSimulator
{
    /// <summary>
    /// Configuration class that holds all connection settings for both OPC DA and RabbitMQ servers
    /// This class is populated from a JSON configuration file
    /// </summary>
    public class ConnectionConfig
    {
        // Unique identifier for the location/facility being monitored
        public string location_id { get; set; }

        // RabbitMQ connection parameters
        public string conn_host { get; set; }        // Hostname or IP address of RabbitMQ server
        public string conn_port { get; set; }        // Port number for RabbitMQ connection (typically 5672)
        public string conn_channel { get; set; }     // Channel prefix used for queue naming
        public string conn_exchange { get; set; }    // Exchange name for message routing
        public string conn_user { get; set; }        // Username for RabbitMQ authentication
        public string conn_vhost { get; set; }       // Virtual host in RabbitMQ
        public string conn_secret { get; set; }      // Password for RabbitMQ authentication

        // OPC DA connection parameters
        public string OpcIpAddress { get; set; }     // IP address of the OPC DA server
        public string ProgramId { get; set; }        // Program ID registered for OPC DA server

        public string opc_simulator_file { get; set; } // To Verify whether to simulate data from file or using OPC
    }

    /// <summary>
    /// Represents a physical or logical device that contains multiple sensors
    /// Each device can have multiple sensors monitoring different parameters
    /// </summary>
    public class Device
    {
        public string device_name { get; set; }      // Friendly name of the device for identification
        public List<Sensor> sensors { get; set; }    // Collection of sensors attached to this device
    }

    /// <summary>
    /// Represents an individual sensor within a device
    /// Each sensor corresponds to a specific OPC DA tag that provides real-time data
    /// </summary>
    public class Sensor
    {
        public string sensor_name { get; set; }      //  name of the sensor for identification
        public string sensor_tag { get; set; }       //  OPC DA tag ID used to read sensor data
    }

    /// <summary>
    /// Main program class that handles the OPC DA data collection and RabbitMQ publishing
    /// Implements a continuous monitoring cycle with configurable polling interval
    /// </summary>
    internal class Program
    {
        // File path for logging with timestamp to ensure unique log files for each run
        private static readonly string logFilePath = $"log_{DateTime.Now:yyyyMMdd_HHmmss}.txt";

        // Cache to store previous tag values for change detection
        // Key: OPC DA tag name, Value: Last recorded value
        private static readonly Dictionary<string, string> previousTagValues = new Dictionary<string, string>();

        private static readonly bool Debug = false;

        private static IConnection rabbitConnection = null;
        private static IModel channel = null;

        /// <summary>
        /// Logs a message to both file and console with timestamp
        /// Ensures consistent logging format across the application
        /// </summary>
        /// <param name="message">The message to be logged</param>


        static void LogToFile(string message)
        {
            string logMessage = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} - {message}";
            File.AppendAllText(logFilePath, logMessage + Environment.NewLine);
            if (Debug)
            {
                Console.WriteLine(logMessage);
            }
        }

        /// <summary>
        /// Loads and deserializes the application configuration from a JSON file
        /// </summary>
        /// <param name="filePath">Path to the configuration JSON file</param>
        /// <returns>Populated ConnectionConfig object with all settings</returns>
        /// <exception cref="JsonException">Thrown when JSON parsing fails</exception>
        /// <exception cref="FileNotFoundException">Thrown when config file is missing</exception>
        static ConnectionConfig LoadConfig(string filePath)
        {
            LogToFile($"Loading configuration ");
            var json = File.ReadAllText(filePath);
            return JsonSerializer.Deserialize<ConnectionConfig>(json);
        }

        /// <summary>
        /// Establishes connection to RabbitMQ server using provided configuration
        /// Creates and configures a channel for message publishing
        /// </summary>
        /// <param name="config">Connection configuration object</param>
        /// <param name="channel">Output parameter that receives the configured channel</param>
        /// <returns>Active RabbitMQ connection object</returns>
        /// <exception cref="Exception">Thrown when connection fails</exception>
        static bool TryConnectToRabbitMq(ConnectionConfig config, out IConnection connection, out IModel channel)
        {
            connection = null;
            channel = null;

            try
            {
                LogToFile("Attempting to connect to data sending server...");

                var factory = new ConnectionFactory
                {
                    HostName = config.conn_host,
                    Port = int.Parse(config.conn_port),
                    UserName = config.conn_user,
                    Password = config.conn_secret,
                    VirtualHost = config.conn_vhost
                };

                connection = factory.CreateConnection();
                channel = connection.CreateModel();

                string queueName = $"{config.conn_channel}{config.location_id}";
                channel.QueueDeclare(queue: queueName, durable: true, exclusive: false, autoDelete: false, arguments: null);

                LogToFile("Successfully connected to data sending server");
                return true;
            }
            catch (Exception ex)
            {
                LogToFile($"Failed to connect to Data sending server: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Establishes connection to OPC DA server using provided configuration
        /// </summary>
        /// <param name="config">Connection configuration object</param>
        /// <returns>Connected OPC DA server object</returns>
        /// <exception cref="Exception">Thrown when connection fails or configuration is invalid</exception>
        static OpcDaServer ConnectToOpcServer(ConnectionConfig config)
        {
            try
            {
                // Validate configuration
                if (string.IsNullOrEmpty(config.OpcIpAddress))
                    throw new Exception("OPC DA IP address is not configured in settings.");

                LogToFile($"Initiating connection to OPC DA server at {config.OpcIpAddress}...");

                // Construct OPC DA URL
                var primaryUrl = $"opcda://{config.OpcIpAddress}/{config.ProgramId}";

                // Create and connect server instance
                var server = new OpcDaServer(new Uri(primaryUrl));
                 server.Connect();
                 Console.WriteLine($"OPCDA Connected - {config.OpcIpAddress}");
                 return server;

            }
            catch (Exception ex)
            {
                Console.WriteLine($"OPCDA Failed - {config.OpcIpAddress}");
                LogToFile($"Failed to connect to OPC DA server: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// Reads values from OPC DA tags for the provided list of sensors
        /// Implements change detection to only record updated values
        /// </summary>
        /// <param name="server">Connected OPC DA server instance</param>
        /// <param name="sensors">List of sensors to read data from</param>
        /// <returns>Dictionary containing tag values keyed by tag name</returns>
        static Dictionary<string, string> ReadDeviceTags(OpcDaServer server, List<Sensor> sensors)
        {
            var tagsData = new Dictionary<string, string>();

            // Validate input parameters
            if (sensors == null || sensors.Count == 0)
            {
                LogToFile("No sensors provided for reading");
                return tagsData;
            }

            try
            {
                // Create a unique group name using timestamp to avoid conflicts
                string uniqueGroupName = $"ReadGroup_{DateTime.Now.Ticks}";

                using (var group = server.AddGroup(uniqueGroupName))
                {
                    // Configure group properties for real-time data acquisition
                    group.UpdateRate = TimeSpan.FromMilliseconds(1000);  // 1 second update rate
                    group.IsActive = true;                               // Activate the group

                    // Filter out sensors with empty tags
                    var validSensors = sensors.Where(s => !string.IsNullOrEmpty(s.sensor_tag)).ToList();
                    // LogToFile($"Processing {validSensors.Count} valid sensors out of {sensors.Count} total");

                    // Create OPC DA item definitions for each sensor
                    var itemDefinitions = validSensors
                        .Select(sensor => new OpcDaItemDefinition
                        {
                            ItemId = sensor.sensor_tag,    // OPC DA tag ID
                            IsActive = true,               // Enable the item
                            AccessPath = string.Empty      // No specific access path needed
                        })
                        .ToList();

                    if (itemDefinitions.Count == 0)
                    {
                        // LogToFile("No valid tag definitions found after filtering");
                        return tagsData;
                    }

                    // Add items to the group and track successful additions
                    var addResults = group.AddItems(itemDefinitions);
                    var validItems = new List<OpcDaItem>();

                    // Process the results of adding items
                    for (int i = 0; i < addResults.Length; i++)
                    {
                        var result = addResults[i];
                        var sensor = validSensors[i];

                        if (result.Error.Succeeded)
                        {
                            validItems.Add(result.Item);
                            // LogToFile($"Successfully added item: {sensor.sensor_tag}");
                        }
                        else
                        {
                            LogToFile($"Failed to add item {sensor.sensor_tag}: {result.Error}");
                            tagsData[sensor.sensor_tag] = "-99";  // Error indicator value
                        }
                    }

                    // Read values for successfully added items
                    if (validItems.Count > 0)
                    {
                        try
                        {
                            // Perform synchronous read from device
                            var readValues = group.Read(validItems, OpcDaDataSource.Device);

                            // Process each read result
                            for (int i = 0; i < readValues.Length; i++)
                            {
                                var item = validItems[i];
                                var value = readValues[i];

                                if (value.Error.Succeeded && value.Value != null)
                                {
                                    try
                                    {
                                        var valueString = Convert.ToString(value.Value);

                                        // Implement change detection
                                        if (previousTagValues.TryGetValue(item.ItemId, out var previousValue))
                                        {
                                            if (previousValue == valueString)
                                            {
                                                // LogToFile($"Skipping unchanged tag {item.ItemId} with value {valueString}");
                                                continue;
                                            }
                                        }

                                        // Update cache and record new value
                                        previousTagValues[item.ItemId] = valueString;
                                        tagsData[item.ItemId] = valueString;
                                        // LogToFile($"Successfully read {item.ItemId}: {valueString}");
                                    }
                                    catch (Exception ex)
                                    {
                                        LogToFile($"Error converting value for {item.ItemId}: {ex.Message}");
                                        tagsData[item.ItemId] = "-99";  // Error indicator value
                                    }
                                }
                                else
                                {
                                    LogToFile($"Error reading {item.ItemId}: {value.Error}");
                                    tagsData[item.ItemId] = "-99";  // Error indicator value
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            LogToFile($"Error during read operation: {ex.Message}");
                            // Mark all items as error in case of group read failure
                            foreach (var item in validItems)
                            {
                                tagsData[item.ItemId] = "-99";  // Error indicator value
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error reading device tags: {ex.Message}");
                // Mark all sensors as error in case of general failure
                foreach (var sensor in sensors.Where(s => !string.IsNullOrEmpty(s.sensor_tag)))
                {
                    tagsData[sensor.sensor_tag] = "-99";  // Error indicator value
                }
            }

            return tagsData;
        }


        /// <summary>
        /// Reads simulated tag values from a JSON file
        /// File format: { "tags": { "tag1": "value1", "tag2": "value2", ... } }
        /// </summary>
        /// <param name="filePath">Path to the simulator JSON file</param>
        /// <returns>Dictionary containing tag values keyed by tag name</returns>
        static Dictionary<string, string> ReadSimulatedTags(string filePath)
        {
            var tagsData = new Dictionary<string, string>();
            try
            {
                LogToFile($"Reading simulated tags ");
                var json = File.ReadAllText(filePath);

                using (JsonDocument doc = JsonDocument.Parse(json))
                {
                    var tagsElement = doc.RootElement.GetProperty("tags");
                    foreach (var tag in tagsElement.EnumerateObject())
                    {
                        tagsData[tag.Name] = tag.Value.GetString() ?? "-99";
                    }
                }

                // LogToFile($"Successfully loaded {tagsData.Count} simulated tags");
            }
            catch (Exception ex)
            {
                LogToFile($"Error reading simulator file: {ex.Message}");
            }
            return tagsData;
        }

        /// <summary>
        /// Loads device and sensor configurations from JSON file
        /// File format: { "data": [ { "device_name": "...", "sensors": [ { "sensor_name": "...", "sensor_tag": "..." } ] } ] }
        /// </summary>
        /// <param name="filePath">Path to the devices configuration file</param>
        /// <returns>List of configured devices with their sensors</returns>
        static List<Device> LoadDevices(string filePath)
        {
            try
            {

                LogToFile($"Loading device configuration ");
                var json = File.ReadAllText(filePath);
                using (JsonDocument doc = JsonDocument.Parse(json))
                {
                    var devices = new List<Device>();
                    var dataArray = doc.RootElement.GetProperty("data");

                    // Parse each device entry
                    foreach (var deviceElement in dataArray.EnumerateArray())
                    {
                        var device = new Device
                        {
                            device_name = deviceElement.GetProperty("device_name").GetString(),
                            sensors = new List<Sensor>()
                        };

                        // Parse sensors for current device
                        var sensorsArray = deviceElement.GetProperty("sensors");
                        foreach (var sensorElement in sensorsArray.EnumerateArray())
                        {
                            var sensorTag = sensorElement.GetProperty("sensor_tag").GetString();
                            // Only add sensors with valid tags
                            if (!string.IsNullOrEmpty(sensorTag))
                            {
                                device.sensors.Add(new Sensor
                                {
                                    sensor_name = sensorElement.GetProperty("sensor_name").GetString(),
                                    sensor_tag = sensorTag
                                });
                            }
                        }

                        devices.Add(device);
                    }

                    //LogToFile($"Successfully loaded {devices.Count} devices");
                    return devices;
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error loading devices configuration: {ex.Message}");
                return new List<Device>();
            }
        }


        /// <summary>
        /// Publishes collected tag data to RabbitMQ queue
        /// Message format: { "location_id": "...", "tags_data": { "tag1": "value1", ... } }
        /// </summary>
        /// <param name="channel">Active RabbitMQ channel</param>
        /// <param name="locationId">Location identifier</param>
        /// <param name="tagsData">Dictionary of tag values to publish</param>
        /// <param name="queueName">Target queue name</param>
        static void SendToRabbitMq(IModel channel, string locationId, Dictionary<string, string> tagsData, string queueName)
        {
            try
            {
                // Create message payload with location ID and tag data
                var data = new { location_id = locationId, tags_data = tagsData };

                // Serialize the payload to JSON
                var messageBody = JsonSerializer.Serialize(data);

                // Convert message to bytes for transmission
                var body = System.Text.Encoding.UTF8.GetBytes(messageBody);

                // Publish message to RabbitMQ queue
                // Using default exchange ("") with queue name as routing key
                channel.BasicPublish(
                    exchange: "",             // Use default exchange
                    routingKey: queueName,    // Queue name acts as routing key
                    basicProperties: null,     // No special message properties
                    body: body                // Message content
                );
                Console.WriteLine("Tags data are posted to DATA RECEIVER");
                LogToFile($"Successfully published  tags to Data Receiving server");
            }
            catch (Exception ex)
            {
                Console.WriteLine("Failed to send the data to DATA RECEIVER");
                LogToFile($"Failed to send data to : {ex.Message}");
                // Don't rethrow - allow the application to continue running
            }
        }

        /// <summary>
        /// Main entry point of the application
        /// Implements continuous monitoring cycle:
        /// 1. Load configuration
        /// 2. Connect to RabbitMQ
        /// 3. For each cycle:
        ///    - Load device configuration
        ///    - Connect to OPC DA server
        ///    - Read device data
        ///    - Publish to RabbitMQ
        ///    - Save to local file
        ///    - Wait for next cycle
        /// </summary>
        /// <param name="args">Command line arguments (not used)</param>
        static void Main(string[] args)
        {
            try
            {
                var config = LoadConfig("config.json");

                Console.WriteLine($"OPCDA Server - {config.OpcIpAddress}");

                bool isRabbitMqConnected = TryConnectToRabbitMq(config, out rabbitConnection, out channel);

                while (true)
                {
                    try
                    {
                        var devices = LoadDevices($"{config.location_id}.json");
                        var allTagsData = new Dictionary<string, string>();

                        if ((config.opc_simulator_file.Length > 0) && File.Exists(config.opc_simulator_file))
                        {
                            allTagsData = ReadSimulatedTags(config.opc_simulator_file);
                        }
                        else
                        {
                            using (var opcServer = ConnectToOpcServer(config))
                            {
                                foreach (var device in devices)
                                {
                                    var deviceTagsData = ReadDeviceTags(opcServer, device.sensors);
                                    foreach (var tagData in deviceTagsData)
                                    {
                                        allTagsData[tagData.Key] = tagData.Value;
                                    }
                                }
                            }
                        }

                        // Always save to local file
                        var outputData = new
                        {
                            location_id = config.location_id,
                            tags_data = allTagsData
                        };

                        var outputPath = Path.Combine(
                            AppDomain.CurrentDomain.BaseDirectory,
                            $"{config.location_id}_data.json"
                        );

                        File.WriteAllText(
                            outputPath,
                            JsonSerializer.Serialize(outputData)
                        );

                        // Only attempt to send to RabbitMQ if connected
                        if (isRabbitMqConnected && channel != null && channel.IsOpen)
                        {
                            string queueName = $"{config.conn_channel}{config.location_id}";
                            SendToRabbitMq(channel, config.location_id, allTagsData, queueName);
                        }
                    }
                    catch (Exception ex)
                    {
                        LogToFile($"Error during monitoring cycle: {ex.Message}");
                    }

                    LogToFile("Waiting for 30 seconds before next monitoring cycle...");
                    System.Threading.Thread.Sleep(30000);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Critical error: {ex.Message}");
                LogToFile($"Critical error - application stopping: {ex.Message}");
                LogToFile($"Stack trace: {ex.StackTrace}");
                throw;
            }
            finally
            {
                channel?.Dispose();
                rabbitConnection?.Dispose();
            }
        }
    }
}