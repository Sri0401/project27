package org.urbanpulse.ingestor;

import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.time.Instant;
import java.util.logging.Logger;

/**
 * Command-line entry point: {@code java -jar ingestor.jar <csv-file>}.
 *
 * <p>Connection settings come from DB_URL, DB_USER and DB_PASSWORD. The job exits with a
 * non-zero code if the file cannot be read, the database is unreachable, or the share of
 * rejected rows exceeds MAX_REJECT_RATIO (default 0.1).
 */
public final class IngestorApp {

    private static final Logger LOG = Logger.getLogger(IngestorApp.class.getName());
    private static final int CONNECT_ATTEMPTS = 10;

    private IngestorApp() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("Usage: java -jar ingestor.jar <csv-file>");
            System.exit(2);
        }
        Path csv = Path.of(args[0]);
        Instant startedAt = Instant.now();

        ParseResult result;
        try (Reader reader = Files.newBufferedReader(csv, StandardCharsets.UTF_8)) {
            result = new CsvSuburbParser().parse(reader);
        }
        result.errors().forEach(error -> LOG.warning("Rejected " + error));

        int total = result.records().size() + result.errors().size();
        double rejectRatio = total == 0 ? 1.0 : (double) result.errors().size() / total;
        double maxRejectRatio = Double.parseDouble(env("MAX_REJECT_RATIO", "0.1"));
        if (rejectRatio > maxRejectRatio) {
            LOG.severe(String.format("Aborting: %.0f%% of rows were rejected (limit %.0f%%)",
                    rejectRatio * 100, maxRejectRatio * 100));
            System.exit(1);
        }

        try (Connection connection = connectWithRetry()) {
            SuburbRepository repository = new SuburbRepository(connection);
            repository.applySchema();
            repository.save(result.records(), csv.getFileName().toString(), result.errors().size(), startedAt);
        }
        LOG.info(String.format("Loaded %d rows from %s (%d rejected)",
                result.records().size(), csv.getFileName(), result.errors().size()));
    }

    /** Retries with a growing delay so the job tolerates a database that is still starting. */
    private static Connection connectWithRetry() throws SQLException, InterruptedException {
        String url = env("DB_URL", "jdbc:postgresql://localhost:5432/urbanpulse");
        String user = env("DB_USER", "urbanpulse");
        String password = env("DB_PASSWORD", "");
        for (int attempt = 1; ; attempt++) {
            try {
                return DriverManager.getConnection(url, user, password);
            } catch (SQLException e) {
                if (attempt == CONNECT_ATTEMPTS) {
                    throw e;
                }
                LOG.info("Database not ready (attempt " + attempt + "): " + e.getMessage());
                Thread.sleep(1000L * attempt);
            }
        }
    }

    private static String env(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : value;
    }
}
