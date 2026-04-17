using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using RabbitMQ.Client;
using TitaniumAS.Opc.Client;
using TitaniumAS.Opc.Client.Da;
using RabbitMQ.Client.Events;
using System.Linq;
using System.Threading.Tasks;
using System.Security;

namespace OpcdaSimulator
{
    /// <summary>
    ///  Represents the configuration settings for the application
    /// </summary>
    public class ConnectionConfig
    {
        // OPC DA Configuration
        public string location_id { get; set; }   // Unique Indentifier the physical location
        public List<string> OpcDaIpAddresses { get; set; } // List of OPC DA IP Addresses to try
        public string ProgramId { get; set; } // OPC DA Server Program ID (ProgID)
        public string opc_simulator_file { get; set; } // Path to Simulator Json If hard coded  checking Data sending for server to server with out opcda connection

        // Rabbit MQ Configuration 
        public string conn_host { get; set; } // RabbitMq Server  hostname
        public string conn_port { get; set; } // RabbitMq Server Port
        public string conn_channel { get; set; } // Base Queue name for Data Messaging 
        public string conn_exchange { get; set; } // RabbitMQ Data Exchange Name
        public string conn_user { get; set; } // RabbitMQ UserName
        public string conn_vhost { get; set; } // RabbitMQ Virtual host
        public string conn_secret { get; set; } // RabbitMQ password 

        // Operational Parameters 
        public bool full_dump { get; set; } // Force full data dump flag
        public bool log_debug { get; set; } // Enable debug logging in Console
        public int FullDumpIntervalMinutes { get; set; } // Interval between full data dumps 
        public string ActivePeriodStart { get; set; } // Active period start time (HH:MM format)
        public string ActivePeriodEnd { get; set; } // Active period end time (HH:MM format)
        public int ActivePollingSeconds { get; set; } // Polling Interval during active period
        public int InactivePollingSeconds { get; set; } // Polling Interval during outside of active period

    }

    /// <summary>
    ///  Represents  a physical device with multiple sensors
    /// </summary>
    public class Device
    {
        public string device_name { get; set; } // Name of the physical device
        public List<Sensor> sensors { get; set; } // List of the sensors in the device 
    }

    /// <summary>
    /// Represents a single sensor with its OPC DA tag mapping 
    /// </summary>
    public class Sensor
    {
        public string sensor_name { get; set; } // Human readable tag name
        public string sensor_tag { get; set; } // OPC DA tag name/path
    }

    internal class Program
    {
        // Logging and state management
        private static readonly string logFilePath = $"log_{DateTime.Now:yyyyMMdd_HHmmss_fff}.txt";
        private static readonly Dictionary<string, string> lastKnownTagValues = new Dictionary<string, string>();
        private static DateTime nextFullDumpTime = DateTime.MinValue; // Track next scheduled full dump
        private static bool Debug;

        // RabbitMQ Connections 
        private static IConnection rabbitConnection = null;
        private static IModel channel = null;

        // Thread Synchroization
        private static readonly object LogLock = new object();
        static readonly object fileLock = new object();  // Define a lock object

        /// <summary>
        /// Thread-safe logging mechanism  with file and console output
        /// </summary>
        /// <param name="message">Message to lg</param>
        static void LogToFile(string message)
        {
            string logMessage = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} - {message}";


            lock (fileLock)  // Lock to prevent simultaneous writes
            {
                try
                {
                    using (StreamWriter writer = new StreamWriter(logFilePath, true, System.Text.Encoding.UTF8, 4096))
                    {
                        writer.WriteLine(logMessage);
                    }
                }
                catch (IOException ex)
                {
                    Console.WriteLine($"Log file write error: {ex.Message}");
                }
            }

            if (Debug)
            {
                lock (LogLock)
                {
                    Console.WriteLine(logMessage);
                }
            }
        }

        /// <summary>
        /// Loads and validates application configuartion
        /// </summary>
        /// <param name="filePath">Path to config.json</param>
        /// <returns>Validated Cofiguartion object</returns>
        /// <exception cref="ArgumentException">Thrown for invalid configuration</exception>
        static ConnectionConfig LoadConfig(string filePath)
        {
            var config = JsonSerializer.Deserialize<ConnectionConfig>(File.ReadAllText(filePath));

            // Validate all required timing parameters
            var validationErrors = new List<string>();

            if (config.FullDumpIntervalMinutes <= 0)
                validationErrors.Add("FullDumpIntervalMinutes must be positive integer");

            if (config.ActivePollingSeconds <= 0)
                validationErrors.Add("ActivePollingSeconds must be positive integer");

            if (config.InactivePollingSeconds <= 0)
                validationErrors.Add("InactivePollingSeconds must be positive integer");

            try
            {
                TimeSpan.Parse(config.ActivePeriodStart);
                TimeSpan.Parse(config.ActivePeriodEnd);
            }
            catch
            {
                validationErrors.Add("ActivePeriodStart/End must be in valid 'HH:mm' format");
            }

            if (validationErrors.Any())
                throw new ArgumentException($"Invalid config: {string.Join(", ", validationErrors)}");

            return config;
        }

        /// <summary>
        /// Establishes connection to RabbitMq server
        /// </summary>
        /// <param name="config">Application Configuartion</param>
        /// <returns>Task with connection success status</returns>
        static Task<bool> TryConnectToRabbitMqAsync(ConnectionConfig config)
        {
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

                rabbitConnection = factory.CreateConnection();
                channel = rabbitConnection.CreateModel();

                string queueName = $"{config.conn_channel}_{config.location_id}";
                channel.QueueDeclare(queue: queueName, durable: true, exclusive: false, autoDelete: false, arguments: null);

                LogToFile("Successfully connected to data sending server");
                return Task.FromResult(true);
            }
            catch (Exception ex)
            {
                LogToFile($"Failed to connect to Data sending server: {ex.Message}");
                return Task.FromResult(false);
            }
        }

        /// <summary>
        ///  Connects to the first available Opc da server from configured IP addresses
        /// </summary>
        /// <param name="config">Application Configuartion</param>
        /// <returns>Connection or Failures status OPC DA Servers </returns>
        static OpcDaServer ConnectToOpcServer(ConnectionConfig config)
        {
            try
            {
                if (config.OpcDaIpAddresses == null || !config.OpcDaIpAddresses.Any())
                    throw new Exception("No OPC DA IP addresses configured in settings.");

                foreach (var ipAddress in config.OpcDaIpAddresses)
                {
                    try
                    {
                        Console.WriteLine($"Attempting to connect to OPCDA Server - {ipAddress}");
                        LogToFile($"Initiating connection to OPC DA server at {ipAddress}...");
                        var serverUrl = $"opcda://{ipAddress}/{config.ProgramId}";
                        var server = new OpcDaServer(new Uri(serverUrl));
                        server.Connect();
                        Console.WriteLine($"OPCDA Connected - {ipAddress}");
                        return server;
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Failed to connect to OPCDA Server - {ipAddress}");
                        LogToFile($"Failed to connect to OPC DA server at {ipAddress}: {ex.Message}");
                    }
                }

                throw new Exception("Failed to connect to any OPC DA server.");
            }
            catch (Exception ex)
            {
                Console.WriteLine("OPCDA Connection Failed");
                LogToFile($"OPC DA server connection failed: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// Reads current values for all configured tags from OPC DA server
        /// </summary>
        /// <param name="server">List of configured devices</param>
        /// <param name="devices">List of configured devices</param>
        /// <returns>Dictionary of tag values with error handling</returns>
        static Dictionary<string, string> ReadAllTags(OpcDaServer server, List<Device> devices)
        {
            var tagsData = new Dictionary<string, string>();

            try
            {
                var allSensors = devices
                    .SelectMany(d => d.sensors)
                    .Where(s => !string.IsNullOrEmpty(s.sensor_tag))
                    .ToList();

                if (allSensors.Count == 0)
                {
                    LogToFile("No valid sensors found to read");
                    return tagsData;
                }

                using (var group = server.AddGroup($"AllTagsGroup_{DateTime.Now.Ticks}"))
                {
                    group.UpdateRate = TimeSpan.FromMilliseconds(100);
                    group.IsActive = true;

                    var itemDefinitions = allSensors.Select(sensor => new OpcDaItemDefinition
                    {
                        ItemId = sensor.sensor_tag,
                        IsActive = true,
                        AccessPath = string.Empty
                    }).ToList();

                    LogToFile($"Adding {itemDefinitions.Count} tags to group");

                    var addResults = group.AddItems(itemDefinitions);
                    var validItems = new List<OpcDaItem>();
                    var validItemToSensor = new Dictionary<OpcDaItem, Sensor>();

                    for (int i = 0; i < addResults.Length; i++)
                    {
                        var result = addResults[i];
                        var sensor = allSensors[i];

                        if (result.Error.Succeeded)
                        {
                            validItems.Add(result.Item);
                            validItemToSensor[result.Item] = sensor;
                        }
                        else
                        {
                            tagsData[sensor.sensor_tag] = "-99";
                            lastKnownTagValues[sensor.sensor_tag] = "-99";
                        }
                    }

                    if (validItems.Count > 0)
                    {
                        LogToFile($"Reading {validItems.Count} valid tags");
                        var readValues = group.Read(validItems.ToArray(), OpcDaDataSource.Device);

                        for (int i = 0; i < readValues.Length; i++)
                        {
                            var item = validItems[i];
                            var value = readValues[i];
                            var sensor = validItemToSensor[item];

                            if (value.Error.Succeeded && value.Value != null)
                            {
                                try
                                {
                                    var valueString = Convert.ToString(value.Value);

                                    if (valueString.Equals("True", StringComparison.OrdinalIgnoreCase))
                                        valueString = "1";
                                    else if (valueString.Equals("False", StringComparison.OrdinalIgnoreCase))
                                        valueString = "0";

                                    if (!lastKnownTagValues.TryGetValue(item.ItemId, out var previousValue) ||
                                        previousValue != valueString)
                                    {
                                        lastKnownTagValues[item.ItemId] = valueString;
                                        tagsData[item.ItemId] = valueString;
                                    }
                                }
                                catch (Exception ex)
                                {
                                    LogToFile($"Error converting value for {item.ItemId}: {ex.Message}");
                                    tagsData[item.ItemId] = "-99";
                                    lastKnownTagValues[item.ItemId] = "-99";
                                }
                            }
                            else
                            {
                                tagsData[item.ItemId] = "-99";
                                lastKnownTagValues[item.ItemId] = "-99";
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error in batch tag reading: {ex.Message}");
                foreach (var device in devices)
                {
                    foreach (var sensor in device.sensors.Where(s => !string.IsNullOrEmpty(s.sensor_tag)))
                    {
                        tagsData[sensor.sensor_tag] = "-99";
                        lastKnownTagValues[sensor.sensor_tag] = "-99";
                    }
                }
            }

            return tagsData;
        }

        /// <summary>
        /// Reads simulated tag values from JSON file with change detection
        /// </summary>
        /// <param name="filePath">Path to simulator JSON file</param>
        /// <returns>Dictionary of changed tag values</returns>
        static Dictionary<string, string> ReadSimulatedTags(string filePath)
        {
            var tagsData = new Dictionary<string, string>();
            try
            {
                LogToFile($"Reading simulated tags");
                var json = File.ReadAllText(filePath);

                using (JsonDocument doc = JsonDocument.Parse(json))
                {
                    var tagsElement = doc.RootElement.GetProperty("tags");
                    foreach (var tag in tagsElement.EnumerateObject())
                    {
                        string newValue = tag.Value.GetString() ?? "-99";

                        // Only include tags that have changed since last reading
                        if (!lastKnownTagValues.TryGetValue(tag.Name, out var previousValue) ||
                            previousValue != newValue)
                        {
                            tagsData[tag.Name] = newValue;
                            lastKnownTagValues[tag.Name] = newValue;  // Update last known value
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error reading simulator file: {ex.Message}");
            }
            return tagsData;
        }

        /// <summary>
        /// Loads device and sensor configuration from JSON file
        /// </summary>
        /// <param name="filePath">Path to device configuration file</param>
        /// <returns>List of configured devices</returns>
        static List<Device> LoadDevices(string filePath)
        {
            try
            {
                LogToFile("Loading device configuration");
                var json = File.ReadAllText(filePath);
                using (JsonDocument doc = JsonDocument.Parse(json))
                {
                    var devices = new List<Device>();
                    var dataArray = doc.RootElement.GetProperty("data");

                    foreach (var deviceElement in dataArray.EnumerateArray())
                    {
                        var device = new Device
                        {
                            device_name = deviceElement.GetProperty("device_name").GetString(),
                            sensors = new List<Sensor>()
                        };

                        var sensorsArray = deviceElement.GetProperty("sensors");
                        foreach (var sensorElement in sensorsArray.EnumerateArray())
                        {
                            var sensorTag = sensorElement.GetProperty("sensor_tag").GetString();
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
        /// Publishes tag data to RabbitMQ queue
        /// </summary>
        /// <param name="channel">RabbitMQ channel</param>
        /// <param name="locationId">Location identifier</param>
        /// <param name="tagsData">Tag values to send</param>
        /// <param name="queueName">Target queue name</param>
        static void SendToRabbitMq(IModel channel, string locationId, Dictionary<string, string> tagsData, string queueName)
        {
            try
            {
                var data = new { location_id = locationId, tags_data = tagsData };
                var messageBody = JsonSerializer.Serialize(data);
                var body = System.Text.Encoding.UTF8.GetBytes(messageBody);

                channel.BasicPublish(
                    exchange: "",
                    routingKey: queueName,
                    basicProperties: null,
                    body: body
                );
                Console.WriteLine("Tags data are posted to DATA RECEIVER");
                LogToFile($"Successfully published tags to Data Receiving server");
            }
            catch (Exception ex)
            {
                Console.WriteLine("Failed to send the data to DATA RECEIVER");
                LogToFile($"Failed to send data to : {ex.Message}");
            }
        }


        /// <summary>
        /// Simulates OPC DA write operations (stubbed implementation)
        /// </summary>
        /// <param name="server">OPC DA server (unused in simulation)</param>
        /// <param name="tagName">Target tag name</param>
        /// <param name="value">Value to write</param>
        /// <returns>Completed task</returns>
        static Task WriteToOpcDaTagAsync(OpcDaServer server, string tagName, string value)
        {
            LogToFile($"[SIMULATED WRITE] Would write value {value} to tag {tagName}");
            return Task.CompletedTask;

            /*try
          {
              if (server == null)
              {
                  LogToFile("Error: OPC DA server is not connected.");
                  return Task.CompletedTask;
              }
              LogToFile("Creating OPC DA group for writing...");
              using (var writeGroup = server.AddGroup($"WriteGroup_{DateTime.Now.Ticks}"))
              {
                  writeGroup.IsActive = true;

                  // Create item definition
                  var itemDefinitions = new List<OpcDaItemDefinition>
          {
              new OpcDaItemDefinition { ItemId = tagName }
          };

                  // Add items to group
                  OpcDaItemResult[] itemResults = writeGroup.AddItems(itemDefinitions);

                  if (itemResults.Length == 0)
                  {
                      LogToFile($"Failed to add item for writing {tagName}: No items added");
                      return Task.CompletedTask;
                  }

                  // Convert value based on type
                  object convertedValue;
                  if (bool.TryParse(value, out bool boolValue))
                  {
                      convertedValue = boolValue;
                  }
                  else if (int.TryParse(value, out int intValue))
                  {
                      convertedValue = intValue;
                  }
                  else if (double.TryParse(value, out double doubleValue))
                  {
                      convertedValue = doubleValue;
                  }
                  else
                  {
                      convertedValue = value;
                  }

                  // Perform write operation
                  HRESULT[] writeResults = writeGroup.Write(new[] { writeGroup.Items[0] }, new[] { convertedValue });

                  if (writeResults[0].Succeeded)
                  {
                      LogToFile($"Successfully wrote value {value} to tag {tagName}");
                  }
                  else
                  {
                      LogToFile($"Failed to write to tag {tagName}: {writeResults[0]}");
                  }
              }
          }
          catch (Exception ex)
          {
              LogToFile($"Error writing to OPC DA tag {tagName}: {ex.Message}");
          }

          return Task.CompletedTask;*/
        }

        /// <summary>
        /// Starts continuous RabbitMQ command listener
        /// </summary>
        /// <param name="config">Application configuration</param>
        static void StartRabbitMqListener(ConnectionConfig config)
        {
            _ = Task.Run(async () =>
            {
                try
                {
                    var factory = new ConnectionFactory
                    {
                        HostName = config.conn_host,
                        Port = int.Parse(config.conn_port),
                        UserName = config.conn_user,
                        Password = config.conn_secret,
                        VirtualHost = config.conn_vhost
                    };

                    while (true)
                    {
                        try
                        {
                            using (var connection = factory.CreateConnection())
                            using (var channel = connection.CreateModel())
                            {
                                string queueName = $"{config.conn_channel}";

                                try
                                {
                                    channel.QueueDeclare(
                                        queue: queueName,
                                        durable: true,
                                        exclusive: false,
                                        autoDelete: false
                                    );
                                }
                                catch (Exception ex)
                                {
                                    LogToFile($"Queue declaration error: {ex.Message}");
                                    continue;
                                }

                                var consumer = new EventingBasicConsumer(channel);
                                consumer.Received += async (model, ea) =>
                                {
                                    try
                                    {
                                        var body = ea.Body.ToArray();
                                        var message = System.Text.Encoding.UTF8.GetString(body);
                                        LogToFile($"Command Data ---> {message}");

                                        using (JsonDocument doc = JsonDocument.Parse(message))
                                        {
                                            var root = doc.RootElement;

                                            if (root.TryGetProperty("command", out JsonElement commandElement) &&
                                                root.TryGetProperty("sensor_tag", out JsonElement tagElement))
                                            {
                                                string command = commandElement.GetString();
                                                string sensorTag = tagElement.GetString();

                                                if (root.TryGetProperty("value", out JsonElement valueElement))
                                                {
                                                    string value = valueElement.GetString();
                                                    await WriteToOpcDaTagAsync(null, sensorTag, value);
                                                }
                                            }
                                            else
                                            {
                                                LogToFile("Invalid command message format");
                                            }
                                        }

                                        channel.BasicAck(ea.DeliveryTag, false);
                                    }
                                    catch (Exception ex)
                                    {
                                        LogToFile($"Error processing message: {ex.Message}");
                                        channel.BasicNack(ea.DeliveryTag, false, true);
                                    }
                                };

                                channel.BasicConsume(
                                    queue: queueName,
                                    autoAck: false,
                                    consumer: consumer
                                );

                                LogToFile($"Listener started for queue: {queueName}");

                                while (connection.IsOpen)
                                {
                                    await Task.Delay(1000);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            LogToFile($"Connection error in listener: {ex.Message}");
                            await Task.Delay(5000);
                        }
                    }
                }
                catch (Exception ex)
                {
                    LogToFile($"Critical error in RabbitMQ Listener: {ex.Message}");
                }
            });
        }


        /// <summary>
        /// Calculates next full dump time based on configured interval
        /// </summary>
        /// <param name="currentTime">Current timestamp</param>
        /// <param name="config">Application configuration</param>
        /// <returns>DateTime for next full dump</returns>
        // Calculate next half-hour interval
        private static DateTime GetNextHalfHour(DateTime currentTime, ConnectionConfig config)
        {
            if (config.FullDumpIntervalMinutes <= 0)
                throw new Exception("Invalid FullDumpIntervalMinutes in config");
            double intervals = currentTime.TimeOfDay.TotalMinutes / config.FullDumpIntervalMinutes;
            DateTime nextDump = currentTime.Date.AddMinutes(Math.Ceiling(intervals) * config.FullDumpIntervalMinutes);

            return nextDump <= currentTime ? nextDump.AddMinutes(config.FullDumpIntervalMinutes) : nextDump;
        }

        /// <summary>
        /// Determines appropriate polling interval based on active period
        /// </summary>
        /// <param name="config">Application configuration</param>
        /// <returns>TimeSpan representing polling interval</returns>
        /// <exception cref="ArgumentException">Thrown for invalid time formats</exception>
        // Determine polling interval based on time of the day                         
        private static TimeSpan GetDelayInterval(ConnectionConfig config)
        {
            // Validate configuration
            if (config.ActivePollingSeconds <= 0 || config.InactivePollingSeconds <= 0)
                throw new ArgumentException("Invalid polling seconds in config");

            try
            {
                TimeSpan now = DateTime.Now.TimeOfDay;
                TimeSpan start = TimeSpan.Parse(config.ActivePeriodStart);
                TimeSpan end = TimeSpan.Parse(config.ActivePeriodEnd);

                return (now >= start && now <= end) ?
                    TimeSpan.FromSeconds(config.ActivePollingSeconds) :
                    TimeSpan.FromSeconds(config.InactivePollingSeconds);
            }
            catch (FormatException ex)
            {
                throw new ArgumentException("Invalid time format in ActivePeriodStart/End", ex);
            }
        }

        /// <summary>
        /// Main application entry point
        /// </summary>
        static async Task Main(string[] args)
        {
            try
            {
                var config = LoadConfig("config.json");
                Debug = config.log_debug;
                nextFullDumpTime = GetNextHalfHour(DateTime.Now, config);
                bool isFirstRun = true;
                StartRabbitMqListener(config);
                bool isRabbitMqConnected = await TryConnectToRabbitMqAsync(config);

                while (true)
                {
                    try
                    {
                        var currentTime = DateTime.Now;
                        bool sendFullDump = isFirstRun || config.full_dump || currentTime >= nextFullDumpTime;

                        var devices = LoadDevices($"{config.location_id}.json");
                        var changedTagsData = new Dictionary<string, string>();

                        if (File.Exists(config.opc_simulator_file))
                        {
                            // SIMULATED TAGS HANDLING
                            var simulatedData = ReadSimulatedTags(config.opc_simulator_file);
                            // Always update last known values from simulator
                            foreach (var tag in simulatedData)
                            {
                                lastKnownTagValues[tag.Key] = tag.Value;
                            }
                            // For simulated tags, consider all tags as "changed"
                            changedTagsData = new Dictionary<string, string>(simulatedData);
                        }
                        else
                        {
                            // REAL OPC TAGS HANDLING
                            using (var opcServer = ConnectToOpcServer(config))
                            {
                                if (opcServer != null)
                                {
                                    changedTagsData = ReadAllTags(opcServer, devices);
                                }
                            }
                        }

                        var dataToSend = sendFullDump
                            ? new Dictionary<string, string>(lastKnownTagValues)
                            : changedTagsData
                                 .Where(kv => kv.Value != "-99") // Filter out "-99" during normal intervals
                                 .ToDictionary(kv => kv.Key, kv => kv.Value);
                        if (sendFullDump)
                        {
                            LogToFile($"Scheduled full dump at {currentTime:HH:mm:ss}");
                            nextFullDumpTime = GetNextHalfHour(currentTime, config);
                        }

                        if (isRabbitMqConnected && channel != null && channel.IsOpen)
                        {
                            string queueName = $"{config.conn_channel}_{config.location_id}";
                            SendToRabbitMq(channel, config.location_id, dataToSend, queueName);
                        }

                        var outputPath = Path.Combine(
                            AppDomain.CurrentDomain.BaseDirectory,
                            $"{config.location_id}_data.json"
                        );
                        File.WriteAllText(outputPath, JsonSerializer.Serialize(new
                        {
                            location_id = config.location_id,
                            tags_data = sendFullDump ? lastKnownTagValues : changedTagsData,
                        }));

                        // Turn off first run flag after completing first cycle
                        isFirstRun = false;
                    }
                    catch (Exception ex)
                    {
                        LogToFile($"Error during monitoring cycle: {ex.Message}");
                    }

                    var delay = GetDelayInterval(config);
                    LogToFile($"Waiting for {delay.TotalSeconds} seconds before next monitoring cycle...");
                    await Task.Delay(delay);
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Critical error: {ex.Message}");
                LogToFile($"Stack trace: {ex.StackTrace}");
            }
            finally
            {
                channel?.Dispose();
                rabbitConnection?.Dispose();
            }
        }
    }
}
