package org.urbanpulse.ingestor;

/** One validated row of suburb indicators. */
public record SuburbRecord(
        String code,
        String name,
        String state,
        double latitude,
        double longitude,
        int population,
        double medianAge,
        int medianWeeklyRent,
        int walkScore,
        double greenSpacePct,
        int ptStops,
        int referenceYear) {
}
