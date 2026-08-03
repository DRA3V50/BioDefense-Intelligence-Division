using System.Text.Json;
using System.Xml.Linq;

internal static class Program
{
    private static readonly string[] VerifiedStatuses =
    {
        "verified",
        "validated",
        "confirmed",
        "intact"
    };

    public static int Main()
    {
        try
        {
            string repositoryRoot = FindRepositoryRoot();

            string currentCasePath = Path.Combine(
                repositoryRoot,
                "data",
                "current_case.json"
            );

            using JsonDocument caseDocument = LoadJsonDocument(
                currentCasePath
            );

            JsonElement caseRoot = caseDocument.RootElement;

            string caseId = GetString(
                caseRoot,
                "case_id",
                "UNKNOWN-CASE"
            );

            string evidenceDirectory = Path.Combine(
                repositoryRoot,
                "evidence",
                caseId
            );

            string manifestPath = Path.Combine(
                evidenceDirectory,
                "evidence_manifest.json"
            );

            string correlationsPath = Path.Combine(
                evidenceDirectory,
                "evidence_correlations.json"
            );

            using JsonDocument manifestDocument = LoadJsonDocument(
                manifestPath
            );

            using JsonDocument correlationsDocument = LoadJsonDocument(
                correlationsPath
            );

            JsonElement manifestRoot = manifestDocument.RootElement;
            JsonElement correlationsRoot = correlationsDocument.RootElement;

            List<JsonElement> evidenceItems = GetArrayItems(
                manifestRoot,
                "evidence_items"
            );

            List<JsonElement> correlations = GetArrayItems(
                correlationsRoot,
                "correlations"
            );

            Dictionary<string, int> findingCounts =
                BuildFindingCounts(correlations);

            DimensionScores scores = BuildDimensionScores(
                caseRoot,
                evidenceItems,
                findingCounts
            );

            int overallScore = CalculateOverallScore(
                scores,
                caseRoot
            );

            int verifiedEvidence = CountVerifiedEvidence(
                evidenceItems
            );

            int pendingReview = CountPendingReview(
                evidenceItems
            );

            object jsonOutput = BuildOutput(
                caseRoot,
                caseId,
                scores,
                overallScore,
                evidenceItems.Count,
                correlations.Count,
                verifiedEvidence,
                pendingReview,
                findingCounts
            );

            XDocument xmlOutput = BuildXmlOutput(
                caseRoot,
                caseId,
                scores,
                overallScore,
                evidenceItems.Count,
                correlations.Count,
                verifiedEvidence,
                pendingReview,
                findingCounts
            );

            string reportsDirectory = Path.Combine(
                repositoryRoot,
                "reports"
            );

            Directory.CreateDirectory(reportsDirectory);

            string jsonOutputPath = Path.Combine(
                reportsDirectory,
                "bioterror_threat_score_csharp.json"
            );

            string xmlOutputPath = Path.Combine(
                reportsDirectory,
                "bioterror_threat_score_csharp.xml"
            );

            JsonSerializerOptions options = new()
            {
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            };

            File.WriteAllText(
                jsonOutputPath,
                JsonSerializer.Serialize(jsonOutput, options)
            );

            xmlOutput.Save(xmlOutputPath);

            Console.WriteLine(
                "C# bioterror threat assessment generated successfully."
            );
            Console.WriteLine($"Case ID: {caseId}");
            Console.WriteLine(
                $"Overall threat score: {overallScore}/100"
            );
            Console.WriteLine(
                $"Overall threat level: {ScoreLabel(overallScore)}"
            );
            Console.WriteLine(
                $"Evidence reviewed: {evidenceItems.Count}"
            );
            Console.WriteLine(
                $"Correlations reviewed: {correlations.Count}"
            );
            Console.WriteLine(
                $"JSON output: {jsonOutputPath}"
            );
            Console.WriteLine(
                $"XML output: {xmlOutputPath}"
            );

            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                "Bioterror threat scoring failed."
            );
            Console.Error.WriteLine(exception.Message);

            return 1;
        }
    }

    private static string FindRepositoryRoot()
    {
        IEnumerable<string> startingPoints = new[]
        {
            Directory.GetCurrentDirectory(),
            AppContext.BaseDirectory
        };

        foreach (string startingPoint in startingPoints)
        {
            DirectoryInfo? directory = new(startingPoint);

            while (directory is not null)
            {
                string casePath = Path.Combine(
                    directory.FullName,
                    "data",
                    "current_case.json"
                );

                if (File.Exists(casePath))
                {
                    return directory.FullName;
                }

                directory = directory.Parent;
            }
        }

        throw new DirectoryNotFoundException(
            "Unable to locate the repository root containing " +
            "data/current_case.json."
        );
    }

    private static JsonDocument LoadJsonDocument(
        string path
    )
    {
        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                $"Required JSON file was not found: {path}",
                path
            );
        }

        string json = File.ReadAllText(path);

        return JsonDocument.Parse(json);
    }

    private static List<JsonElement> GetArrayItems(
        JsonElement root,
        string propertyName
    )
    {
        if (
            root.ValueKind != JsonValueKind.Object
            || !root.TryGetProperty(
                propertyName,
                out JsonElement arrayElement
            )
            || arrayElement.ValueKind != JsonValueKind.Array
        )
        {
            return new List<JsonElement>();
        }

        return arrayElement
            .EnumerateArray()
            .Select(item => item.Clone())
            .ToList();
    }

    private static string GetString(
        JsonElement element,
        string propertyName,
        string defaultValue = "Not specified"
    )
    {
        if (
            element.ValueKind != JsonValueKind.Object
            || !element.TryGetProperty(
                propertyName,
                out JsonElement value
            )
        )
        {
            return defaultValue;
        }

        return value.ValueKind switch
        {
            JsonValueKind.String =>
                value.GetString() ?? defaultValue,

            JsonValueKind.Number =>
                value.GetRawText(),

            JsonValueKind.True =>
                "true",

            JsonValueKind.False =>
                "false",

            _ =>
                defaultValue
        };
    }

    private static int GetInt(
        JsonElement element,
        string propertyName,
        int defaultValue = 0
    )
    {
        if (
            element.ValueKind != JsonValueKind.Object
            || !element.TryGetProperty(
                propertyName,
                out JsonElement value
            )
        )
        {
            return defaultValue;
        }

        if (
            value.ValueKind == JsonValueKind.Number
            && value.TryGetInt32(out int integerValue)
        )
        {
            return integerValue;
        }

        if (
            value.ValueKind == JsonValueKind.Number
            && value.TryGetDouble(out double doubleValue)
        )
        {
            return Convert.ToInt32(doubleValue);
        }

        if (
            value.ValueKind == JsonValueKind.String
            && double.TryParse(
                value.GetString(),
                out double parsedValue
            )
        )
        {
            return Convert.ToInt32(parsedValue);
        }

        return defaultValue;
    }

    private static Dictionary<string, int> BuildFindingCounts(
        IEnumerable<JsonElement> correlations
    )
    {
        Dictionary<string, int> counts = new(
            StringComparer.OrdinalIgnoreCase
        );

        foreach (JsonElement correlation in correlations)
        {
            string finding = GetString(
                correlation,
                "finding",
                "Unspecified Investigative Finding"
            );

            counts[finding] = counts.GetValueOrDefault(
                finding
            ) + 1;
        }

        return counts;
    }

    private static int CountMatchingFindings(
        IReadOnlyDictionary<string, int> findingCounts,
        params string[] keywords
    )
    {
        int total = 0;

        foreach (
            KeyValuePair<string, int> finding
            in findingCounts
        )
        {
            if (
                keywords.Any(
                    keyword =>
                        finding.Key.Contains(
                            keyword,
                            StringComparison.OrdinalIgnoreCase
                        )
                )
            )
            {
                total += finding.Value;
            }
        }

        return total;
    }

    private static int CountMatchingEvidence(
        IEnumerable<JsonElement> evidenceItems,
        params string[] keywords
    )
    {
        int total = 0;

        foreach (JsonElement item in evidenceItems)
        {
            string searchableText = string.Join(
                " ",
                GetString(item, "artifact_type", ""),
                GetString(item, "source_system", ""),
                GetString(item, "category", ""),
                GetString(item, "description", ""),
                GetString(item, "vendor", "")
            );

            if (
                keywords.Any(
                    keyword =>
                        searchableText.Contains(
                            keyword,
                            StringComparison.OrdinalIgnoreCase
                        )
                )
            )
            {
                total++;
            }
        }

        return total;
    }

    private static int CountVerifiedEvidence(
        IEnumerable<JsonElement> evidenceItems
    )
    {
        return evidenceItems.Count(
            item =>
                VerifiedStatuses.Contains(
                    GetString(
                        item,
                        "integrity_status",
                        ""
                    ).Trim().ToLowerInvariant()
                )
        );
    }

    private static int CountPendingReview(
        IEnumerable<JsonElement> evidenceItems
    )
    {
        string[] pendingTerms =
        {
            "pending",
            "awaiting",
            "unreviewed"
        };

        return evidenceItems.Count(
            item =>
            {
                string reviewStatus = GetString(
                    item,
                    "review_status",
                    ""
                );

                return pendingTerms.Any(
                    term =>
                        reviewStatus.Contains(
                            term,
                            StringComparison.OrdinalIgnoreCase
                        )
                );
            }
        );
    }

    private static DimensionScores BuildDimensionScores(
        JsonElement caseRoot,
        List<JsonElement> evidenceItems,
        Dictionary<string, int> findingCounts
    )
    {
        string severity = GetString(
            caseRoot,
            "severity",
            "UNKNOWN"
        ).ToUpperInvariant();

        int riskScore = Clamp(
            GetInt(
                caseRoot,
                "risk_score",
                SeverityBaseScore(severity)
            )
        );

        int caseConfidence = Clamp(
            GetInt(
                caseRoot,
                "confidence",
                50
            )
        );

        int affectedAssets = Math.Max(
            0,
            GetInt(
                caseRoot,
                "affected_assets",
                0
            )
        );

        int credential = CountMatchingFindings(
            findingCounts,
            "credential",
            "authentication",
            "account",
            "identity"
        );

        int network = CountMatchingFindings(
            findingCounts,
            "network",
            "command-and-control",
            "command and control",
            "c2",
            "exfiltration"
        );

        int laboratory = CountMatchingFindings(
            findingCounts,
            "laboratory system",
            "laboratory information system",
            "laboratory modification",
            "lims"
        );

        int research = CountMatchingFindings(
            findingCounts,
            "research data",
            "genomic",
            "genome",
            "data integrity",
            "biomedical"
        );

        int biosecurity = CountMatchingFindings(
            findingCounts,
            "biosecurity",
            "containment",
            "policy violation"
        );

        int facility = CountMatchingFindings(
            findingCounts,
            "facility access",
            "unauthorized facility",
            "physical access",
            "insider"
        );

        int actor = CountMatchingFindings(
            findingCounts,
            "known threat actor",
            "threat actor indicator",
            "attribution"
        );

        int workstation = CountMatchingFindings(
            findingCounts,
            "workstation compromise",
            "research workstation",
            "endpoint compromise"
        );

        int laboratoryArtifacts = CountMatchingEvidence(
            evidenceItems,
            "laboratory",
            "lims",
            "specimen",
            "biosecurity"
        );

        int researchArtifacts = CountMatchingEvidence(
            evidenceItems,
            "research",
            "genomic",
            "genome",
            "sequence",
            "biomedical"
        );

        int accessArtifacts = CountMatchingEvidence(
            evidenceItems,
            "authentication",
            "access control",
            "credential",
            "vpn"
        );

        int networkArtifacts = CountMatchingEvidence(
            evidenceItems,
            "network",
            "firewall",
            "connection",
            "proxy",
            "dns"
        );

        int credentialSignal = SaturatingSignal(
            credential,
            20
        );

        int networkSignal = SaturatingSignal(
            network,
            25
        );

        int laboratorySignal = SaturatingSignal(
            laboratory,
            25
        );

        int researchSignal = SaturatingSignal(
            research,
            25
        );

        int biosecuritySignal = SaturatingSignal(
            biosecurity,
            25
        );

        int facilitySignal = SaturatingSignal(
            facility,
            15
        );

        int actorSignal = SaturatingSignal(
            actor,
            12
        );

        int workstationSignal = SaturatingSignal(
            workstation,
            20
        );

        int laboratoryArtifactSignal = SaturatingSignal(
            laboratoryArtifacts,
            30
        );

        int researchArtifactSignal = SaturatingSignal(
            researchArtifacts,
            30
        );

        int accessArtifactSignal = SaturatingSignal(
            accessArtifacts,
            25
        );

        int networkArtifactSignal = SaturatingSignal(
            networkArtifacts,
            30
        );

        int assetSignal = SaturatingSignal(
            affectedAssets,
            20
        );

        int findingDiversitySignal = SaturatingSignal(
            findingCounts.Count,
            12
        );

        int threatActorIntent = WeightedScore(
            (riskScore, 0.45),
            (actorSignal, 0.20),
            (networkSignal, 0.10),
            (researchSignal, 0.10),
            (laboratorySignal, 0.10),
            (biosecuritySignal, 0.05)
        );

        int threatActorCapability = WeightedScore(
            (riskScore, 0.40),
            (credentialSignal, 0.15),
            (networkSignal, 0.15),
            (workstationSignal, 0.10),
            (laboratorySignal, 0.10),
            (actorSignal, 0.05),
            (assetSignal, 0.05)
        );

        int biologicalTargetValue = WeightedScore(
            (riskScore, 0.35),
            (researchSignal, 0.25),
            (laboratorySignal, 0.20),
            (biosecuritySignal, 0.15),
            (laboratoryArtifactSignal, 0.025),
            (researchArtifactSignal, 0.025)
        );

        int laboratoryAndSpecimenImpact = WeightedScore(
            (riskScore, 0.40),
            (laboratorySignal, 0.20),
            (researchSignal, 0.15),
            (biosecuritySignal, 0.15),
            (facilitySignal, 0.10)
        );

        int publicHealthRisk = WeightedScore(
            (riskScore, 0.45),
            (biosecuritySignal, 0.20),
            (laboratorySignal, 0.15),
            (researchSignal, 0.10),
            (facilitySignal, 0.10)
        );

        int cyberToPhysicalEscalation = WeightedScore(
            (riskScore, 0.40),
            (facilitySignal, 0.20),
            (laboratorySignal, 0.15),
            (biosecuritySignal, 0.15),
            (networkSignal, 0.05),
            (accessArtifactSignal, 0.05)
        );

        int attributionConfidence = WeightedScore(
            (caseConfidence, 0.75),
            (actorSignal, 0.15),
            (networkArtifactSignal, 0.05),
            (findingDiversitySignal, 0.05)
        );

        string containmentPhase = GetString(
            caseRoot,
            "containment_phase",
            GetString(
                caseRoot,
                "status",
                "Unknown"
            )
        );

        int containmentAdjustment = 0;

        if (
            ContainsAny(
                containmentPhase,
                "recovery",
                "contained",
                "remediation",
                "monitoring"
            )
        )
        {
            containmentAdjustment = 10;
        }

        if (
            ContainsAny(
                containmentPhase,
                "active compromise",
                "escalation",
                "uncontained"
            )
        )
        {
            containmentAdjustment = -10;
        }

        int verifiedCount = CountVerifiedEvidence(
            evidenceItems
        );

        double integrityRatio = evidenceItems.Count == 0
            ? 0.0
            : (double) verifiedCount / evidenceItems.Count;

        int containmentConfidence = Clamp(
            Convert.ToInt32(
                Math.Round(
                    caseConfidence * 0.55
                    + integrityRatio * 25
                    + containmentAdjustment
                )
            )
        );

        return new DimensionScores(
            threatActorIntent,
            threatActorCapability,
            biologicalTargetValue,
            laboratoryAndSpecimenImpact,
            publicHealthRisk,
            cyberToPhysicalEscalation,
            attributionConfidence,
            containmentConfidence
        );
    }

    private static int CalculateOverallScore(
        DimensionScores scores,
        JsonElement caseRoot
    )
    {
        double threatComposite =
            (
                scores.ThreatActorIntent
                + scores.ThreatActorCapability
                + scores.BiologicalTargetValue
                + scores.LaboratoryAndSpecimenImpact
                + scores.PublicHealthRisk
                + scores.CyberToPhysicalEscalation
            )
            / 6.0;

        int caseRiskScore = Clamp(
            GetInt(
                caseRoot,
                "risk_score",
                SeverityBaseScore(
                    GetString(
                        caseRoot,
                        "severity",
                        "UNKNOWN"
                    )
                )
            )
        );

        double calibratedScore =
            threatComposite * 0.45
            + caseRiskScore * 0.50
            + scores.AttributionConfidence * 0.10
            - scores.ContainmentConfidence * 0.05;

        return Clamp(
            Convert.ToInt32(
                Math.Round(calibratedScore)
            )
        );
    }

    private static object BuildOutput(
        JsonElement caseRoot,
        string caseId,
        DimensionScores scores,
        int overallScore,
        int evidenceCount,
        int correlationCount,
        int verifiedEvidence,
        int pendingReview,
        IReadOnlyDictionary<string, int> findingCounts
    )
    {
        Dictionary<string, object> dimensions = new()
        {
            ["threatActorIntent"] = BuildDimension(
                scores.ThreatActorIntent,
                false
            ),
            ["threatActorCapability"] = BuildDimension(
                scores.ThreatActorCapability,
                false
            ),
            ["biologicalTargetValue"] = BuildDimension(
                scores.BiologicalTargetValue,
                false
            ),
            ["laboratoryAndSpecimenImpact"] = BuildDimension(
                scores.LaboratoryAndSpecimenImpact,
                false
            ),
            ["publicHealthRisk"] = BuildDimension(
                scores.PublicHealthRisk,
                false
            ),
            ["cyberToPhysicalEscalation"] = BuildDimension(
                scores.CyberToPhysicalEscalation,
                false
            ),
            ["attributionConfidence"] = BuildDimension(
                scores.AttributionConfidence,
                true
            ),
            ["containmentConfidence"] = BuildDimension(
                scores.ContainmentConfidence,
                true
            )
        };

        List<object> topFindings = findingCounts
            .OrderByDescending(item => item.Value)
            .ThenBy(item => item.Key)
            .Take(12)
            .Select(
                item => (object) new
                {
                    finding = item.Key,
                    correlations = item.Value
                }
            )
            .ToList();

        return new
        {
            generatedAt = DateTime.UtcNow.ToString(
                "yyyy-MM-dd HH:mm 'UTC'"
            ),
            engine = new
            {
                name = "BioDefense C# Bioterror Threat Scoring Engine",
                version = "1.1.0",
                runtime = ".NET 8",
                scoringModel = "Risk-Anchored Saturating Evidence Model"
            },
            investigation = new
            {
                caseId,
                campaignId = GetString(
                    caseRoot,
                    "campaign_id"
                ),
                operation = GetString(
                    caseRoot,
                    "operation"
                ),
                classification = GetString(
                    caseRoot,
                    "classification"
                ),
                threatFamily = GetString(
                    caseRoot,
                    "threat_family"
                ),
                severity = GetString(
                    caseRoot,
                    "severity"
                ),
                priority = GetString(
                    caseRoot,
                    "priority"
                ),
                riskScore = GetInt(
                    caseRoot,
                    "risk_score"
                ),
                confidence = GetInt(
                    caseRoot,
                    "confidence"
                ),
                containmentPhase = GetString(
                    caseRoot,
                    "containment_phase"
                ),
                affectedPlatform = GetString(
                    caseRoot,
                    "affected_platform"
                ),
                affectedAssets = GetInt(
                    caseRoot,
                    "affected_assets"
                )
            },
            assessment = new
            {
                overallScore,
                overallLevel = ScoreLabel(overallScore),
                dimensions
            },
            evidenceBasis = new
            {
                evidenceRecords = evidenceCount,
                correlationRecords = correlationCount,
                integrityVerifiedRecords = verifiedEvidence,
                pendingAnalystReview = pendingReview,
                priorityFindings = topFindings
            },
            analyticalNotice =
                "This output is generated from fictional defensive " +
                "cyber-biothreat simulation data for portfolio and " +
                "educational use. It is not a real-world biological " +
                "threat determination."
        };
    }


    private static XDocument BuildXmlOutput(
        JsonElement caseRoot,
        string caseId,
        DimensionScores scores,
        int overallScore,
        int evidenceCount,
        int correlationCount,
        int verifiedEvidence,
        int pendingReview,
        IReadOnlyDictionary<string, int> findingCounts
    )
    {
        XElement dimensions = new(
            "Dimensions",
            BuildXmlDimension(
                "ThreatActorIntent",
                scores.ThreatActorIntent,
                false
            ),
            BuildXmlDimension(
                "ThreatActorCapability",
                scores.ThreatActorCapability,
                false
            ),
            BuildXmlDimension(
                "BiologicalTargetValue",
                scores.BiologicalTargetValue,
                false
            ),
            BuildXmlDimension(
                "LaboratoryAndSpecimenImpact",
                scores.LaboratoryAndSpecimenImpact,
                false
            ),
            BuildXmlDimension(
                "PublicHealthRisk",
                scores.PublicHealthRisk,
                false
            ),
            BuildXmlDimension(
                "CyberToPhysicalEscalation",
                scores.CyberToPhysicalEscalation,
                false
            ),
            BuildXmlDimension(
                "AttributionConfidence",
                scores.AttributionConfidence,
                true
            ),
            BuildXmlDimension(
                "ContainmentConfidence",
                scores.ContainmentConfidence,
                true
            )
        );

        XElement priorityFindings = new(
            "PriorityFindings",
            findingCounts
                .OrderByDescending(item => item.Value)
                .ThenBy(item => item.Key)
                .Take(12)
                .Select(
                    item => new XElement(
                        "Finding",
                        new XElement(
                            "Name",
                            item.Key
                        ),
                        new XElement(
                            "Correlations",
                            item.Value
                        )
                    )
                )
        );

        return new XDocument(
            new XDeclaration(
                "1.0",
                "utf-8",
                null
            ),
            new XElement(
                "BioterrorThreatAssessment",
                new XElement(
                    "GeneratedAt",
                    DateTime.UtcNow.ToString(
                        "yyyy-MM-dd HH:mm 'UTC'"
                    )
                ),
                new XElement(
                    "Engine",
                    new XElement(
                        "Name",
                        "BioDefense C# Bioterror Threat Scoring Engine"
                    ),
                    new XElement(
                        "Version",
                        "1.1.0"
                    ),
                    new XElement(
                        "Runtime",
                        ".NET 8"
                    ),
                    new XElement(
                        "ScoringModel",
                        "Risk-Anchored Saturating Evidence Model"
                    )
                ),
                new XElement(
                    "Investigation",
                    new XElement(
                        "CaseId",
                        caseId
                    ),
                    new XElement(
                        "CampaignId",
                        GetString(
                            caseRoot,
                            "campaign_id"
                        )
                    ),
                    new XElement(
                        "Operation",
                        GetString(
                            caseRoot,
                            "operation"
                        )
                    ),
                    new XElement(
                        "Classification",
                        GetString(
                            caseRoot,
                            "classification"
                        )
                    ),
                    new XElement(
                        "ThreatFamily",
                        GetString(
                            caseRoot,
                            "threat_family"
                        )
                    ),
                    new XElement(
                        "Severity",
                        GetString(
                            caseRoot,
                            "severity"
                        )
                    ),
                    new XElement(
                        "Priority",
                        GetString(
                            caseRoot,
                            "priority"
                        )
                    ),
                    new XElement(
                        "RiskScore",
                        GetInt(
                            caseRoot,
                            "risk_score"
                        )
                    ),
                    new XElement(
                        "Confidence",
                        GetInt(
                            caseRoot,
                            "confidence"
                        )
                    ),
                    new XElement(
                        "ContainmentPhase",
                        GetString(
                            caseRoot,
                            "containment_phase"
                        )
                    ),
                    new XElement(
                        "AffectedPlatform",
                        GetString(
                            caseRoot,
                            "affected_platform"
                        )
                    ),
                    new XElement(
                        "AffectedAssets",
                        GetInt(
                            caseRoot,
                            "affected_assets"
                        )
                    )
                ),
                new XElement(
                    "Assessment",
                    new XElement(
                        "OverallScore",
                        overallScore
                    ),
                    new XElement(
                        "OverallLevel",
                        ScoreLabel(overallScore)
                    ),
                    dimensions
                ),
                new XElement(
                    "EvidenceBasis",
                    new XElement(
                        "EvidenceRecords",
                        evidenceCount
                    ),
                    new XElement(
                        "CorrelationRecords",
                        correlationCount
                    ),
                    new XElement(
                        "IntegrityVerifiedRecords",
                        verifiedEvidence
                    ),
                    new XElement(
                        "PendingAnalystReview",
                        pendingReview
                    ),
                    priorityFindings
                ),
                new XElement(
                    "AnalyticalNotice",
                    "This output is generated from fictional defensive " +
                    "cyber-biothreat simulation data for portfolio and " +
                    "educational use. It is not a real-world biological " +
                    "threat determination."
                )
            )
        );
    }

    private static XElement BuildXmlDimension(
        string name,
        int score,
        bool confidenceDimension
    )
    {
        return new XElement(
            "Dimension",
            new XAttribute(
                "Name",
                name
            ),
            new XElement(
                "Score",
                score
            ),
            new XElement(
                "Level",
                confidenceDimension
                    ? ConfidenceLabel(score)
                    : ScoreLabel(score)
            )
        );
    }

    private static object BuildDimension(
        int score,
        bool confidenceDimension
    )
    {
        return new
        {
            score,
            level = confidenceDimension
                ? ConfidenceLabel(score)
                : ScoreLabel(score)
        };
    }

    private static int SaturatingSignal(
        int count,
        int midpoint
    )
    {
        if (count <= 0)
        {
            return 0;
        }

        int safeMidpoint = Math.Max(
            1,
            midpoint
        );

        return Clamp(
            Convert.ToInt32(
                Math.Round(
                    100.0
                    * count
                    / (
                        count
                        + safeMidpoint
                    )
                )
            )
        );
    }

    private static int WeightedScore(
        params (int Value, double Weight)[] components
    )
    {
        double weightedTotal = components.Sum(
            component =>
                Clamp(component.Value)
                * component.Weight
        );

        return Clamp(
            Convert.ToInt32(
                Math.Round(weightedTotal)
            )
        );
    }

    private static int SeverityBaseScore(
        string severity
    )
    {
        return severity.ToUpperInvariant() switch
        {
            "CRITICAL" => 85,
            "HIGH" => 70,
            "MODERATE" => 50,
            "LOW" => 25,
            _ => 35
        };
    }

    private static int Clamp(
        int value
    )
    {
        return Math.Max(
            0,
            Math.Min(100, value)
        );
    }

    private static bool ContainsAny(
        string value,
        params string[] terms
    )
    {
        return terms.Any(
            term =>
                value.Contains(
                    term,
                    StringComparison.OrdinalIgnoreCase
                )
        );
    }

    private static string ScoreLabel(
        int score
    )
    {
        return score switch
        {
            >= 85 => "CRITICAL",
            >= 70 => "HIGH",
            >= 45 => "ELEVATED",
            >= 20 => "GUARDED",
            _ => "LOW"
        };
    }

    private static string ConfidenceLabel(
        int score
    )
    {
        return score switch
        {
            >= 85 => "HIGH",
            >= 60 => "MODERATE",
            >= 35 => "LOW",
            _ => "LIMITED"
        };
    }

    private sealed record DimensionScores(
        int ThreatActorIntent,
        int ThreatActorCapability,
        int BiologicalTargetValue,
        int LaboratoryAndSpecimenImpact,
        int PublicHealthRisk,
        int CyberToPhysicalEscalation,
        int AttributionConfidence,
        int ContainmentConfidence
    );
}
