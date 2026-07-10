using System;
using System.IO;
using System.Text.Json;

namespace BioDefenseIntelligenceDivision
{
    internal class ExposureParser
    {
        static void Main(string[] args)
        {
            const string caseFile = "data/current_case.json";

            if (!File.Exists(caseFile))
            {
                Console.WriteLine("Investigation file not found.");
                return;
            }

            string json = File.ReadAllText(caseFile);

            using JsonDocument document = JsonDocument.Parse(json);

            JsonElement root = document.RootElement;

            Console.WriteLine("==========================================");
            Console.WriteLine(" BioDefense Intelligence Division");
            Console.WriteLine(" Investigation Overview");
            Console.WriteLine("==========================================");

            Print(root, "case_id", "Case ID");
            Print(root, "operation", "Operation");
            Print(root, "classification", "Classification");
            Print(root, "threat_family", "Threat Family");
            Print(root, "severity", "Severity");
            Print(root, "status", "Status");
            Print(root, "containment_phase", "Phase");
            Print(root, "affected_platform", "Platform");
            Print(root, "device_family", "Device");
            Print(root, "network_zone", "Network Zone");
            Print(root, "vendor", "Vendor");
            Print(root, "lead_analyst", "Lead Analyst");
            Print(root, "confidence", "Confidence");
            Print(root, "risk_score", "Risk Score");

            Console.WriteLine("------------------------------------------");
            Console.WriteLine("Assessment");
            Console.WriteLine("------------------------------------------");

            if (root.TryGetProperty("assessment", out JsonElement assessment))
            {
                Console.WriteLine(assessment.GetString());
            }

            Console.WriteLine("==========================================");
        }

        static void Print(JsonElement root, string key, string label)
        {
            if (root.TryGetProperty(key, out JsonElement value))
            {
                Console.WriteLine($"{label,-18}: {value}");
            }
        }
    }
}
