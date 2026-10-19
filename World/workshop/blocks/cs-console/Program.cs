// A console program in C#. Run: dotnet run
using System;
using System.Collections.Generic;

class Program
{
    static int? ReadInt(string prompt)
    {
        while (true)
        {
            Console.Write(prompt);
            string? s = Console.ReadLine();
            if (s == null) return null;
            if (int.TryParse(s.Trim(), out int v)) return v;
            Console.WriteLine("Please type a whole number.");
        }
    }

    static void Main()
    {
        var scores = new List<int>();
        Console.WriteLine("== My C# program ==");
        while (true)
        {
            Console.WriteLine("\n1) Add a score\n2) Show the average\n0) Quit");
            int? c = ReadInt("Choose: ");
            if (c == null || c == 0) break;
            if (c == 1)
            {
                int? s = ReadInt("Score: ");
                if (s != null) scores.Add(s.Value);
            }
            else if (c == 2)
            {
                if (scores.Count == 0) Console.WriteLine("No scores yet.");
                else
                {
                    double sum = 0;
                    foreach (int s in scores) sum += s;
                    Console.WriteLine($"Average of {scores.Count}: {sum / scores.Count:F1}");
                }
            }
            else Console.WriteLine($"No option {c}.");
        }
        Console.WriteLine("Bye.");
    }
}
