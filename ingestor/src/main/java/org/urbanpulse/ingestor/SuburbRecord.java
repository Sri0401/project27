package org.urbanpulse.ingestor;

/** One validated row of area indicators (an ABS SA2, roughly one suburb). */
public record SuburbRecord(
        String code,
        String name,
        String state,
        double latitude,
        double longitude,
        double areaSqkm,
        int population,
        double medianAge,
        int medianWeeklyRent,
        int medianHouseholdIncome,
        double greenSpacePct,
        int ptStops,
        double roadCrashesPerYear,
        int referenceYear) {
}
