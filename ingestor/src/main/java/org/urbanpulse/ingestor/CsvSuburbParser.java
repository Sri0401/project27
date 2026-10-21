package org.urbanpulse.ingestor;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Parses and validates suburb indicator CSV files.
 *
 * <p>Columns are matched by header name, so their order does not matter. A bad row is
 * rejected and reported, and parsing carries on with the next row.
 */
public final class CsvSuburbParser {

    static final List<String> REQUIRED_COLUMNS = List.of(
            "code", "name", "state", "latitude", "longitude", "area_sqkm", "population", "median_age",
            "median_weekly_rent", "median_household_income", "green_space_pct", "pt_stops", "road_crashes_per_year",
            "reference_year");

    private static final Pattern CODE_PATTERN = Pattern.compile("[A-Za-z0-9-]{1,16}");

    public ParseResult parse(Reader input) throws IOException {
        List<SuburbRecord> records = new ArrayList<>();
        List<String> errors = new ArrayList<>();
        Set<String> seenCodes = new HashSet<>();

        try (BufferedReader reader = new BufferedReader(input)) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                throw new IllegalArgumentException("CSV file is empty");
            }
            Map<String, Integer> columns = indexHeader(splitLine(stripBom(headerLine)));

            String line;
            int lineNumber = 1;
            while ((line = reader.readLine()) != null) {
                lineNumber++;
                if (line.isBlank()) {
                    continue;
                }
                try {
                    SuburbRecord record = toRecord(splitLine(line), columns);
                    if (!seenCodes.add(record.code())) {
                        throw new IllegalArgumentException("duplicate code '" + record.code() + "'");
                    }
                    records.add(record);
                } catch (IllegalArgumentException e) {
                    errors.add("line " + lineNumber + ": " + e.getMessage());
                }
            }
        }
        return new ParseResult(records, errors);
    }

    private static Map<String, Integer> indexHeader(List<String> header) {
        Map<String, Integer> columns = new HashMap<>();
        for (int i = 0; i < header.size(); i++) {
            columns.put(header.get(i).trim().toLowerCase(), i);
        }
        List<String> missing = REQUIRED_COLUMNS.stream().filter(c -> !columns.containsKey(c)).toList();
        if (!missing.isEmpty()) {
            throw new IllegalArgumentException("CSV header is missing columns: " + missing);
        }
        return columns;
    }

    private static SuburbRecord toRecord(List<String> fields, Map<String, Integer> columns) {
        Row row = new Row(fields, columns);

        String code = row.text("code");
        if (!CODE_PATTERN.matcher(code).matches()) {
            throw new IllegalArgumentException("code '" + code + "' must be 1-16 letters, digits or '-'");
        }
        return new SuburbRecord(
                code,
                row.text("name"),
                row.text("state").toUpperCase(),
                row.decimal("latitude", -90, 90),
                row.decimal("longitude", -180, 180),
                row.decimal("area_sqkm", 0.0001, 1_000_000),
                row.integer("population", 0, Integer.MAX_VALUE),
                row.decimal("median_age", 0, 120),
                row.integer("median_weekly_rent", 0, Integer.MAX_VALUE),
                row.integer("median_household_income", 0, Integer.MAX_VALUE),
                row.decimal("green_space_pct", 0, 100),
                row.integer("pt_stops", 0, Integer.MAX_VALUE),
                row.decimal("road_crashes_per_year", 0, 1_000_000),
                row.integer("reference_year", 1900, 2100));
    }

    /** Splits one CSV line, honouring double-quoted fields and doubled-quote escapes. */
    static List<String> splitLine(String line) {
        List<String> fields = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (inQuotes) {
                if (c == '"' && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else if (c == '"') {
                    inQuotes = false;
                } else {
                    current.append(c);
                }
            } else if (c == '"') {
                inQuotes = true;
            } else if (c == ',') {
                fields.add(current.toString());
                current.setLength(0);
            } else {
                current.append(c);
            }
        }
        fields.add(current.toString());
        return fields;
    }

    private static String stripBom(String line) {
        return line.startsWith("﻿") ? line.substring(1) : line;
    }

    /** Typed, range-checked access to the fields of one CSV row. */
    private record Row(List<String> fields, Map<String, Integer> columns) {

        String text(String column) {
            int index = columns.get(column);
            String value = index < fields.size() ? fields.get(index).trim() : "";
            if (value.isEmpty()) {
                throw new IllegalArgumentException(column + " is required");
            }
            return value;
        }

        int integer(String column, int min, int max) {
            String value = text(column);
            int parsed;
            try {
                parsed = Integer.parseInt(value);
            } catch (NumberFormatException e) {
                throw new IllegalArgumentException(column + " '" + value + "' is not a whole number");
            }
            return checkRange(column, parsed, min, max);
        }

        double decimal(String column, double min, double max) {
            String value = text(column);
            double parsed;
            try {
                parsed = Double.parseDouble(value);
            } catch (NumberFormatException e) {
                throw new IllegalArgumentException(column + " '" + value + "' is not a number");
            }
            if (!Double.isFinite(parsed)) {
                throw new IllegalArgumentException(column + " '" + value + "' is not a number");
            }
            return checkRange(column, parsed, min, max);
        }

        private static <T extends Comparable<T>> T checkRange(String column, T value, T min, T max) {
            if (value.compareTo(min) < 0 || value.compareTo(max) > 0) {
                throw new IllegalArgumentException(column + " " + value + " is outside " + min + ".." + max);
            }
            return value;
        }
    }
}
