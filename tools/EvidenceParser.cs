using System;
using System.IO;

namespace BioDefenseIntelligenceDivision
{
    internal class EvidenceParser
    {
        static void Main(string[] args)
        {
            const string evidenceFile = "evidence/evidence_log.csv";

            if (!File.Exists(evidenceFile))
            {
                Console.WriteLine("Evidence log not found.");
                return;
            }

            string[] lines = File.ReadAllLines(evidenceFile);

            if (lines.Length <= 1)
            {
                Console.WriteLine("No evidence has been collected.");
                return;
            }

            Console.WriteLine("=========================================");
            Console.WriteLine(" BioDefense Intelligence Division");
            Console.WriteLine(" Evidence Collection Summary");
            Console.WriteLine("=========================================");

            Console.WriteLine($"Evidence Items: {lines.Length - 1}");
            Console.WriteLine();

            for (int i = 1; i < lines.Length; i++)
            {
                string[] columns = lines[i].Split(',');

                if (columns.Length < 5)
                    continue;

                Console.WriteLine($"Evidence ID : {columns[0]}");
                Console.WriteLine($"Date        : {columns[1]}");
                Console.WriteLine($"Case ID     : {columns[2]}");
                Console.WriteLine($"Artifact    : {columns[3]}");
                Console.WriteLine($"Assessment  : {columns[4]}");
                Console.WriteLine("-----------------------------------------");
            }

            Console.WriteLine("Evidence review complete.");
        }
    }
}
