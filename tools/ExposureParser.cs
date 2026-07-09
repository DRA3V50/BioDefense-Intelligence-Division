using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace BioDefenseIntelligenceDivision
{
    class ExposureParser
    {
        static void Main()
        {
            string input = "evidence/evidence_log.csv";
            string output = "reconstruction/evidence_summary.md";

            if (!File.Exists(input))
            {
                Console.WriteLine("Evidence log not found.");
                return;
            }

            var lines = File.ReadAllLines(input);

            var summary = new Dictionary<string, int>();

            foreach (var line in lines.Skip(1))
            {
                if (string.IsNullOrWhiteSpace(line))
                    continue;

                var columns = line.Split(',');

                if (columns.Length < 4)
                    continue;

                string artifact = columns[3].Trim();

                if (!summary.ContainsKey(artifact))
                    summary[artifact] = 0;

                summary[artifact]++;
            }

            using (StreamWriter writer = new StreamWriter(output))
            {
                writer.WriteLine("# Evidence Summary");
                writer.WriteLine();

                writer.WriteLine("| Artifact Type | Count |");
                writer.WriteLine("|--------------|------:|");

                foreach (var item in summary.OrderByDescending(x => x.Value))
                {
                    writer.WriteLine($"| {item.Key} | {item.Value} |");
                }

                writer.WriteLine();
                writer.WriteLine($"Generated: {DateTime.UtcNow:yyyy-MM-dd HH:mm} UTC");
            }

            Console.WriteLine("Evidence summary generated.");
        }
    }
}
