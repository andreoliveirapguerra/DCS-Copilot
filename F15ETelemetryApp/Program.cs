using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Text.RegularExpressions;
using System.Text.Json;
using System.Net.Http;





class Program
{
    private static System.Timers.Timer sendTimer;

    private static readonly List<string> telemetryBuffer = new();
    private static readonly HttpClient httpClient = new();
    private static Dictionary<string, string> labelToDescription;

    public static void StartTelemetrySender()
    {
        sendTimer = new System.Timers.Timer(5000); // 5 seconds
        sendTimer.Elapsed += SendBufferedTelemetry;
        sendTimer.AutoReset = true;
        sendTimer.Start();
    }

    private static async void SendBufferedTelemetry(object sender, System.Timers.ElapsedEventArgs e)
    {
        if (telemetryBuffer.Count == 0) return;

        var payload = new { telemetry = telemetryBuffer.ToArray() };
        string json = JsonSerializer.Serialize(payload);

        try
        {
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            var response = await httpClient.PostAsync("http://127.0.0.1:5000/telemetry", content);

            if (response.IsSuccessStatusCode)
                Console.WriteLine($"✅ Sent {telemetryBuffer.Count} telemetry entries");
            else
                Console.WriteLine($"❌ Failed to send telemetry: {response.StatusCode}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Error sending telemetry: {ex.Message}");
        }

        telemetryBuffer.Clear();
    }



    static void Main(string[] args)
    {

        Console.WriteLine("🚀 Launching F-15E Telemetry Application");

        //int DCSBIOS_PORT = 7778; // default DCS-BIOS export port
        //string DCSBIOS_HOST = "127.0.0.1";
        ////var TelemetryReader = new F15E_DCSBIOS_EmbeddedTelemetryReader();

        //TcpClient tcpClient = new TcpClient(DCSBIOS_HOST, DCSBIOS_PORT);
        ////IPEndPoint remoteEP = new IPEndPoint(IPAddress.Any, DCSBIOS_PORT);
        //NetworkStream stream = tcpClient.GetStream();

        //Console.WriteLine("🔗 Connecting to DCS-BIOS on " + DCSBIOS_HOST + ":" + DCSBIOS_PORT);


        // ####################### START TESTS 1

        const int listenPort = 5010;
        const string multicastIP = "239.255.50.10";

        using UdpClient client = new UdpClient();

        client.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
        client.Client.Bind(new IPEndPoint(IPAddress.Any, listenPort));
        client.JoinMulticastGroup(IPAddress.Parse(multicastIP));

        Console.WriteLine("🎯 Listening for DCS-BIOS telemetry on 239.255.50.10:5010");

        IPEndPoint remoteEP = new IPEndPoint(IPAddress.Any, 0);
        if (remoteEP == null) Console.WriteLine("❌ Failed to create remote endpoint. Check if DCS-BIOS is running and port is correct.");
        else Console.WriteLine("✅ Remote endpoint created successfully.");


        Console.WriteLine("Loading address map from Addresses.h and JSON files...");
        var addressMap = F15E_DCSBIOS_EmbeddedTelemetryReader.LoadAddressMap("Addresses.h");

        Console.WriteLine("Starting Timer to send telemetry data every 5 seconds...");
        StartTelemetrySender();

        labelToDescription = F15E_DCSBIOS_EmbeddedTelemetryReader.LoadLabelDescriptions();

        while (true)
        {
            try
            {
                byte[] data = null;

                //int b = stream.ReadByte();
                //if (b == -1) break;


                data = client.Receive(ref remoteEP);
                //Console.WriteLine($"📦 Received {data.Length} bytes from {remoteEP}");

                //data = F15E_DCSBIOS_EmbeddedTelemetryReader.GetData(remoteEP, udpClient);
                //F15E_DCSBIOS_EmbeddedTelemetryReader.ParseDCSBIOSPacket(data, addressMap);

                F15E_DCSBIOS_EmbeddedTelemetryReader.ParseDCSBIOSPacket(
                    data,
                    addressMap,
                    labelToDescription,
                    telemetryBuffer
                    );

            }
            catch (Exception ex)
            {
                Console.WriteLine("❌ Error Parsing: " + ex.Message);
            }

            Thread.Sleep(1);
        }


        //F15E_DCSBIOS_EmbeddedTelemetryReader.Start();
    }
}

public class F15E_DCSBIOS_EmbeddedTelemetryReader
{
    static readonly int DCSBIOS_PORT = 7778; // default DCS-BIOS export port
    static readonly string DCSBIOS_HOST = "127.0.0.1";

    static readonly Dictionary<string, ushort> state = new Dictionary<string, ushort>();


    public static byte[] GetData(IPEndPoint remoteEP, UdpClient udpClient)
    {
        //Console.WriteLine("🔗 Connecting to DCS-BIOS on " + DCSBIOS_HOST + ":" + DCSBIOS_PORT);



        //while (true)
        //{
        //    try
        //    {
        //        byte[] data = udpClient.Receive(ref remoteEP);
        //        ParseDCSBIOSPacket(data);
        //    }
        //    catch (Exception ex)
        //    {
        //        Console.WriteLine("❌ Error receiving: " + ex.Message);
        //    }

        //    Thread.Sleep(10);
        //}
        byte[] data = null;
        try
        {
            data = udpClient.Receive(ref remoteEP);
            //ParseDCSBIOSPacket(data);
        }
        catch (Exception ex)
        {
            Console.WriteLine("❌ Error receiving: " + ex.Message);
        }

        return data;
    }

    public static Dictionary<ushort, string> LoadAddressMap(string headerFilePath)
    {
        var map = new Dictionary<ushort, string>();

        // Load from Addresses.h
        if (File.Exists(headerFilePath))
        {
            string[] lines = File.ReadAllLines(headerFilePath);
            foreach (var line in lines)
            {
                var match = Regex.Match(line, @"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)");
                if (match.Success)
                {
                    string label = match.Groups[1].Value;
                    ushort address = Convert.ToUInt16(match.Groups[2].Value, 16);
                    map[address] = label;
                }
            }
        }

        // Helper method to parse JSON file
        void ParseJsonFile(string path)
        {
            if (!File.Exists(path)) return;

            string json = File.ReadAllText(path);
            var doc = JsonDocument.Parse(json);

            foreach (var category in doc.RootElement.EnumerateObject())
            {
                foreach (var entry in category.Value.EnumerateObject())
                {
                    var control = entry.Value;

                    if (control.TryGetProperty("outputs", out var outputs))
                    {
                        foreach (var output in outputs.EnumerateArray())
                        {
                            if (output.TryGetProperty("address", out var addrProp) &&
                                output.TryGetProperty("identifier", out var labelProp))
                            {
                                ushort addr = (ushort)addrProp.GetInt32();
                                string label = labelProp.GetString() ?? "UNKNOWN";
                                map[addr] = label;
                            }
                        }
                    }
                }
            }
        }

        // Load from F-15E.json and CommonData.json
        ParseJsonFile("F-15E.json");
        ParseJsonFile("CommonData.json");
        //LoadLabelDescr/*iptions();*/

        return map;
    }

    public static void ParseDCSBIOSPacket(
        byte[] data,
        Dictionary<ushort, string> addressMap,
        Dictionary<string, string> labelToDescription,
        List<string> telemetryBuffer
        )
    {
        int index = 0;

        if (data != null)
        {
            while (index + 4 <= data.Length)
            {
                // Parse the address and value from the byte array
                ushort address = (ushort)(data[index] + (data[index + 1] << 8));
                ushort value = (ushort)(data[index + 2] + (data[index + 3] << 8));

                string labelValue;

                if (addressMap.TryGetValue(address, out var label))
                {
                    labelValue = label;
                    string description = labelToDescription.ContainsKey(label) ? labelToDescription[label] : "No description";
                    string entry = $"{label} ({description}) (0x{address:X4}) = {value}";
                    telemetryBuffer.Add(entry);

                    Console.WriteLine($"📡 {labelValue} (0x{address:X4}) = {value}");
                }
                else
                {
                    labelValue = "UNKNOWN";
                    //Console.WriteLine($"⚠️ Unknown label -> 0x{address:X4} = {value}");
                }

                // Example: you now have both `labelValue` and `value` as variables you can use
                // Optionally save to dictionary, write to a file, update GUI, etc.

                index += 4;
            }
        }
        else
        {
            Console.WriteLine("❌ Received null data packet");
        }
    }

    // Define this globally


    public static Dictionary<string, string> LoadLabelDescriptions()
    {
        Dictionary<string, string> labelToDescription = new();

        string commonDataJson = File.ReadAllText("CommonData.json");
        string f15Json = File.ReadAllText("F-15E.json");

        var commonData = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(commonDataJson);
        var f15Data = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(f15Json);

        foreach (var pair in commonData)
        {
            if (pair.Value.TryGetProperty("description", out var desc))
                labelToDescription[pair.Key] = desc.GetString();
        }

        foreach (var pair in f15Data)
        {
            if (pair.Value.TryGetProperty("description", out var desc))
                labelToDescription[pair.Key] = desc.GetString();
        }
        return labelToDescription;
    }


}


