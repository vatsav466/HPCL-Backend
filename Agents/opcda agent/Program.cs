using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using RabbitMQ.Client;
using TitaniumAS.Opc.Client.Da;
using TitaniumAS.Opc.Client.Common;

namespace OpcdaSimulator
{
    // Connection Configuration Class
    public class ConnectionConfig
    {
        public string location_id { get; set; }
        public string conn_host { get; set; }
        public string conn_port { get; set; }
        public string conn_channel { get; set; }
        public string conn_exchange { get; set; }
        public string conn_user { get; set; }
        public string conn_vhost { get; set; }
        public string conn_secret { get; set; }
        public string[] OpcIpAddresses { get; set; }
        public string connection_parameter { get; set; }
        public string ProgramId { get; set; }
        public string central_server { get; set; }
        public string Api_Key { get; set; }
    }

    // Sensor Data Class
    public class SensorData
    {
        public string sensor_tag { get; set; }
    }

    // Main Program Class
    internal class Program
    {
        private static readonly string logFilePath = $"log_{DateTime.Now:yyyyMMdd_HHmmss}.txt";
        private static readonly HttpClient httpClient = new HttpClient();

        // Download JSON from central server
        static async Task<string> DownloadLocationJson(ConnectionConfig config, string locationId)
        {
            try
            {
                LogToFile($"Attempting to download JSON for location {locationId} from central server...");

                // Construct the full URL
                string fullUrl = $"{config.central_server}?location_id={locationId}";

                // Create the request with API key
                using (var request = new HttpRequestMessage(HttpMethod.Get, fullUrl))
                {
                    request.Headers.Add("X-API-Key", config.Api_Key);

                    using (var response = await httpClient.SendAsync(request))
                    {
                        response.EnsureSuccessStatusCode();
                        string jsonContent = await response.Content.ReadAsStringAsync();

                        // Determine the application base directory
                        string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;

                        // Construct the output file path
                        string outputFilePath = Path.Combine(baseDirectory, $"{locationId}.json");

                        // Save the downloaded JSON to a local file
                        File.WriteAllText(outputFilePath, jsonContent);

                        LogToFile($"Successfully downloaded JSON for location {locationId} at {outputFilePath}");
                        return outputFilePath;
                    }
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error downloading JSON from API: {ex.Message}");
                throw;
            }
        }

        static List<SensorData> LoadSensorTags(string filePath)
        {
            LogToFile($"Loading sensor tags from {filePath}");
            try
            {
                var json = File.ReadAllText(filePath);
                using (JsonDocument doc = JsonDocument.Parse(json))
                {
                    var sensorTags = new List<SensorData>();
                    foreach (var device in doc.RootElement.GetProperty("data").EnumerateArray())
                    {
                        if (device.TryGetProperty("sensors", out var sensorsArray))
                        {
                            foreach (var sensor in sensorsArray.EnumerateArray())
                            {
                                var sensorTag = sensor.GetProperty("sensor_tag").GetString();
                                sensorTags.Add(new SensorData { sensor_tag = sensorTag });
                            }
                        }
                    }
                    return sensorTags;
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error reading sensor tags from {filePath}: {ex.Message}");
                return new List<SensorData>();
            }
        }

        static ConnectionConfig LoadConfig(string filePath)
        {
            LogToFile($"Loading configuration...");
            var json = File.ReadAllText(filePath);
            return JsonSerializer.Deserialize<ConnectionConfig>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
        }

        static IConnection ConnectToRabbitMq(ConnectionConfig config, out IModel channel)
        {
            try
            {
                LogToFile("Connecting to RabbitMQ...");
                var factory = new ConnectionFactory
                {
                    HostName = config.conn_host,
                    Port = int.Parse(config.conn_port),
                    UserName = config.conn_user,
                    Password = config.conn_secret,
                    VirtualHost = config.conn_vhost
                };

                var connection = factory.CreateConnection();
                channel = connection.CreateModel();
                channel.QueueDeclare(queue: $"{config.conn_channel}{config.location_id}", durable: true, exclusive: false, autoDelete: false);
                return connection;
            }
            catch (Exception ex)
            {
                LogToFile($"Failed to connect to RabbitMQ: {ex.Message}");
                throw;
            }
        }

        static OpcDaServer ConnectToOpcServer(ConnectionConfig config)
        {
            if (config.OpcIpAddresses == null || config.OpcIpAddresses.Length == 0)
            {
                throw new Exception("No OPC DA IP addresses configured.");
            }

            foreach (var ipAddress in config.OpcIpAddresses)
            {
                try
                {
                    LogToFile($"Trying to connect to OPC DA server at {ipAddress} with timeout {config.connection_parameter} seconds...");

                    var primaryUrl = $"opcda://{ipAddress}/{config.ProgramId}";

                    // Create a new OPC DA server instance
                    var server = new OpcDaServer(new Uri(primaryUrl));

                    // Set a timeout for the connection attempt
                    using (var cancellationTokenSource = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(int.Parse(config.connection_parameter))))
                    {
                        server.Connect(); 
                    }

                    LogToFile($"Successfully connected to OPC DA server at {ipAddress}");
                    return server;
                }
                catch (Exception ex)
                {
                    LogToFile($"Failed to connect to OPC DA server at {ipAddress}: {ex.Message}");
                }
            }

            // If all connection attempts fail
            LogToFile("Failed to connect to any configured OPC DA servers.");
            throw new Exception("Failed to connect to any configured OPC DA servers.");
        }


        static object ReadOpcValue(OpcDaServer server, string sensorTag)
        {
            try
            {
                var group = server.AddGroup("ReadGroup");
                var itemDefinition = new OpcDaItemDefinition { ItemId = sensorTag };
                var items = new List<OpcDaItemDefinition> { itemDefinition };
                group.AddItems(items);
                var values = group.Read(group.Items, OpcDaDataSource.Device);
                return values?.Length > 0 ? values[0]?.Value : null;
            }
            catch (Exception ex)
            {
                LogToFile($"Error reading OPC value for {sensorTag}: {ex.Message}");
                return null;
            }
        }

        static Dictionary<string, object> LoadFallbackData(List<SensorData> sensorTags, string filePath)
        {
            var jsonData = File.ReadAllText(filePath);
            var data = JsonSerializer.Deserialize<Dictionary<string, object>>(jsonData);
            var fallbackData = new Dictionary<string, object>();
            foreach (var sensor in sensorTags)
            {
                if (data != null && data.TryGetValue(sensor.sensor_tag, out var value))
                {
                    fallbackData[sensor.sensor_tag] = value;
                }
            }
            return fallbackData;
        }

        static void SendToRabbitMq(IModel channel, object data, string queueName)
        {
            try
            {
                var messageBody = JsonSerializer.Serialize(data);
                var body = System.Text.Encoding.UTF8.GetBytes(messageBody);
                channel.BasicPublish(exchange: "", routingKey: queueName, basicProperties: null, body: body);
            }
            catch (Exception ex)
            {
                LogToFile($"Failed to send data to RabbitMQ: {ex.Message}");
            }
        }

        static void LogToFile(string message)
        {
            string logMessage = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} - {message}";
            File.AppendAllText(logFilePath, logMessage + Environment.NewLine);
            Console.WriteLine(logMessage);
        }

        static async Task MainAsync(string[] args)
        {
            try
            {
                var config = LoadConfig("C:\\Users\\manoh\\source\\repos\\OpcdaSimulator\\OpcdaSimulator\\config.json");
                string jsonFilePath = await DownloadLocationJson(config, config.location_id);
                var sensorTags = LoadSensorTags(jsonFilePath);

                using (var rabbitConnection = ConnectToRabbitMq(config, out var channel))
                {
                    var tagsData = new Dictionary<string, object>();
                    try
                    {
                        using (var opcServer = ConnectToOpcServer(config))
                        {
                            foreach (var sensor in sensorTags)
                            {
                                var value = ReadOpcValue(opcServer, sensor.sensor_tag);
                                if (value != null) tagsData[sensor.sensor_tag] = value;
                            }
                        }
                    }
                    catch
                    {
                        tagsData = LoadFallbackData(sensorTags, "data.json");
                    }

                    var dataToSend = new { location_id = config.location_id, tags_data = tagsData };
                    SendToRabbitMq(channel, dataToSend, $"{config.conn_channel}{config.location_id}");
                }
            }
            catch (Exception ex)
            {
                LogToFile($"Error: {ex.Message}");
            }
        }

        static void Main(string[] args)
        {
            MainAsync(args).GetAwaiter().GetResult();
        }
    }
}