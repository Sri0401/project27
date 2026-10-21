package org.urbanpulse.ingestor;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;

class CsvSuburbParserTest {

    private static final String HEADER = String.join(",", CsvSuburbParser.REQUIRED_COLUMNS);
    private final CsvSuburbParser parser = new CsvSuburbParser();

    private ParseResult parse(String... lines) throws IOException {
        return parser.parse(new StringReader(String.join("\n", lines)));
    }

    @Test
    void parsesValidRow() throws IOException {
        ParseResult result = parse(HEADER, "206071142,Fitzroy,vic,-37.80,144.97,1.3779,10431,35,451,2194,0.87,35,41.8,2021");

        assertEquals(List.of(), result.errors());
        SuburbRecord r = result.records().get(0);
        assertEquals("Fitzroy", r.name());
        assertEquals("VIC", r.state(), "state is upper-cased");
        assertEquals(1.3779, r.areaSqkm());
        assertEquals(2194, r.medianHouseholdIncome());
        assertEquals(0.87, r.greenSpacePct());
        assertEquals(41.8, r.roadCrashesPerYear());
    }

    @Test
    void columnOrderDoesNotMatter() throws IOException {
        List<String> reversed = new ArrayList<>(CsvSuburbParser.REQUIRED_COLUMNS);
        Collections.reverse(reversed);
        ParseResult result = parse(String.join(",", reversed),
                "2021,41.8,35,0.87,2194,451,35,10431,1.3779,144.97,-37.80,VIC,Fitzroy,206071142");

        assertEquals("206071142", result.records().get(0).code());
        assertEquals(10431, result.records().get(0).population());
    }

    @Test
    void rejectsBadRowsButKeepsGoodOnes() throws IOException {
        ParseResult result = parse(HEADER,
                "A1,Good,VIC,-37,144,2.5,100,30,400,1500,10,5,3.2,2021",
                "A2,Bad green,VIC,-37,144,2.5,100,30,400,1500,150,5,3.2,2021",
                "A3,Bad number,VIC,-37,144,2.5,lots,30,400,1500,10,5,3.2,2021",
                "A1,Duplicate,VIC,-37,144,2.5,100,30,400,1500,10,5,3.2,2021",
                "",
                "bad code!,Bad code,VIC,-37,144,2.5,100,30,400,1500,10,5,3.2,2021");

        assertEquals(1, result.records().size());
        assertEquals(4, result.errors().size());
        assertTrue(result.errors().get(0).startsWith("line 3: green_space_pct 150"), result.errors().get(0));
        assertTrue(result.errors().get(1).contains("population 'lots' is not a whole number"));
        assertTrue(result.errors().get(2).contains("duplicate code 'A1'"));
        assertTrue(result.errors().get(3).startsWith("line 7: code"), result.errors().get(3));
    }

    @Test
    void handlesQuotedFields() {
        assertEquals(List.of("A1", "Smith, North", "say \"hi\""),
                CsvSuburbParser.splitLine("A1,\"Smith, North\",\"say \"\"hi\"\"\""));
    }

    @Test
    void failsFastOnMissingColumns() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> parse("code,name", "A1,X"));
        assertTrue(e.getMessage().contains("median_household_income"));
    }
}
