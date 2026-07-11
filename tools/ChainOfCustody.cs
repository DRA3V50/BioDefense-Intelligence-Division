using System;
using System.IO;

namespace BioDefenseIntelligenceDivision
{
    internal class ChainOfCustody
    {
        static void Main(string[] args)
        {
            const string custodyFile = "evidence/chain_of_custody.csv";

            if (!File.Exists(custodyFile))
            {
                Console.WriteLine("Chain of custody file not found.");
                return;
            }

            string[] records = File.ReadAllLines(custodyFile);

            if (records.Length <= 1)
            {
                Console.WriteLine("No custody records available.");
                return;
            }

            Console.WriteLine("=========================================");
            Console.WriteLine(" BioDefense Intelligence Division");
            Console.WriteLine(" Chain of Custody Review");
            Console.WriteLine("=========================================");

            int validRecords = 0;

            for (int i = 1; i < records.Length; i++)
            {
                string[] fields = records[i].Split(',');

                if (fields.Length < 5)
                    continue;

                validRecords++;

                Console.WriteLine($"Evidence ID : {fields[0]}");
                Console.WriteLine($"Collected   : {fields[1]}");
                Console.WriteLine($"Examiner    : {fields[2]}");
                Console.WriteLine($"Location    : {fields[3]}");
                Console.WriteLine($"Status      : {fields[4]}");
                Console.WriteLine("-----------------------------------------");
            }

            Console.WriteLine();
            Console.WriteLine($"Verified Records : {validRecords}");
            Console.WriteLine("Chain of custody review complete.");
        }
    }
}
