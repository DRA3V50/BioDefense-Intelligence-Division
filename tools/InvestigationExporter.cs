using System;
using System.IO;
using System.Text;
using System.Text.Json;

namespace BioDefenseIntelligenceDivision
{
    internal class InvestigationExporter
    {
        static void Main(string[] args)
        {
            const string caseFile = "data/current_case.json";

            if (!File.Exists(caseFile))
            {
                Console.WriteLine("Current investigation not found.");
                return;
            }

            string json = File.ReadAllText(caseFile);

            using JsonDocument document = JsonDocument.Parse(json);

            JsonElement root = document.RootElement;

            StringBuilder report = new StringBuilder();

            report.AppendLine("# BioDefense Intelligence Division");
            report.AppendLine("## Operational Investigation Brief");
            report.AppendLine();

            Add(report, root, "case_id", "Case ID");
            Add(report, root, "operation", "Operation");
            Add(report, root, "classification", "Classification");
            Add(report, root, "threat_family", "Threat Family");
            Add(report, root, "severity", "Severity");
            Add(report, root, "status", "Status");
            Add(report, root, "containment_phase", "Phase");
            Add(report, root, "affected_platform", "Platform");
            Add(report, root, "device_family", "Device");
            Add(report, root, "vendor", "Vendor");
            Add(report, root, "network_zone", "Network Zone");
            Add(report, root, "lead_analyst", "Lead Analyst");
            Add(report, root, "confidence", "Confidence");
            Add(report, root, "risk_score", "Risk Score");

            report.AppendLine();
            report.AppendLine("Assessment");
            report.AppendLine("--------------------------------");

            if (root.TryGetProperty("assessment", out JsonElement assessment))
                report.AppendLine(assessment.GetString());

            report.AppendLine();
            report.AppendLine("--------------------------------");

            Include(report, "intelligence/active_findings.md");
            Include(report, "intelligence/campaign_summary.md");
            Include(report, "intelligence/ioc_database.md");
            Include(report, "reconstruction/forensic_summary.md");
            Include(report, "reconstruction/device_profile.md");
            Include(report, "reconstruction/exposure_timeline.md");

            File.WriteAllText(
                "cases/Operational_Brief.md",
                report.ToString()
            );

            Console.WriteLine("Operational briefing exported.");
        }

        static void Add(
            StringBuilder report,
            JsonElement root,
            string key,
            string label)
        {
            if (root.TryGetProperty(key, out JsonElement value))
                report.AppendLine($"{label}: {value}");
        }

        static void Include(
            StringBuilder report,
            string file)
        {
            if (!File.Exists(file))
                return;

            report.AppendLine();
            report.AppendLine("================================");
            report.AppendLine(Path.GetFileName(file));
            report.AppendLine("================================");
            report.AppendLine();

            report.AppendLine(File.ReadAllText(file));
        }
    }
}
