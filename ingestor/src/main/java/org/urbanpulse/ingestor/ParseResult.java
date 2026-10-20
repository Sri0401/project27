package org.urbanpulse.ingestor;

import java.util.List;

/** Valid records plus a readable message for every rejected line. */
public record ParseResult(List<SuburbRecord> records, List<String> errors) {

    public ParseResult {
        records = List.copyOf(records);
        errors = List.copyOf(errors);
    }
}
