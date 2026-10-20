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
        ParseResult result = parse(HEADER, "MEL03,Fitzroy,vic,-37.79,144.97,10900,34.2,520,96,9.8,70,2026");

        assertEquals(List.of(), result.errors());
        SuburbRecord r = result.records().get(0);
        assertEquals("Fitzroy", r.name());
        assertEquals("VIC", r.state(), "state is upper-cased");
        assertEquals(96, r.walkScore());
        assertEquals(9.8, r.greenSpacePct());
    }

    @Test
    void columnOrderDoesNotMatter() throws IOException {
        List<String> reversed = new ArrayList<>(CsvSuburbParser.REQUIRED_COLUMNS);
        Collections.reverse(reversed);
        ParseResult result = parse(String.join(",", reversed),
                "2026,70,9.8,96,520,34.2,10900,144.97,-37.79,VIC,Fitzroy,MEL03");

        assertEquals("MEL03", result.records().get(0).code());
        assertEquals(10900, result.records().get(0).population());
    }

    @Test
    void rejectsBadRowsButKeepsGoodOnes() throws IOException {
        ParseResult result = parse(HEADER,
                "A1,Good,VIC,-37,144,100,30,400,50,10,5,2026",
                "A2,Bad walk,VIC,-37,144,100,30,400,150,10,5,2026",
                "A3,Bad number,VIC,-37,144,lots,30,400,50,10,5,2026",
                "A1,Duplicate,VIC,-37,144,100,30,400,50,10,5,2026",
                "",
                "bad code!,Bad code,VIC,-37,144,100,30,400,50,10,5,2026");

        assertEquals(1, result.records().size());
        assertEquals(4, result.errors().size());
        assertTrue(result.errors().get(0).startsWith("line 3: walk_score 150"), result.errors().get(0));
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
        assertTrue(e.getMessage().contains("walk_score"));
    }
}
