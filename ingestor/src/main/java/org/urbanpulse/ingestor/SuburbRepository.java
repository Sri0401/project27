package org.urbanpulse.ingestor;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;

/** JDBC access to the suburb tables. */
public final class SuburbRepository {

    private static final String UPSERT_SQL = """
            INSERT INTO suburb_indicators (code, name, state, latitude, longitude, population, median_age,
                median_weekly_rent, walk_score, green_space_pct, pt_stops, reference_year, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                state = EXCLUDED.state,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                population = EXCLUDED.population,
                median_age = EXCLUDED.median_age,
                median_weekly_rent = EXCLUDED.median_weekly_rent,
                walk_score = EXCLUDED.walk_score,
                green_space_pct = EXCLUDED.green_space_pct,
                pt_stops = EXCLUDED.pt_stops,
                reference_year = EXCLUDED.reference_year,
                updated_at = now()
            """;

    private static final String RUN_SQL = """
            INSERT INTO ingestion_runs (source, rows_loaded, rows_rejected, started_at)
            VALUES (?, ?, ?, ?)
            """;

    private final Connection connection;

    public SuburbRepository(Connection connection) {
        this.connection = connection;
    }

    public void applySchema() throws SQLException, IOException {
        try (InputStream in = SuburbRepository.class.getResourceAsStream("/schema.sql")) {
            if (in == null) {
                throw new IOException("schema.sql is missing from the jar");
            }
            try (Statement statement = connection.createStatement()) {
                statement.execute(new String(in.readAllBytes(), StandardCharsets.UTF_8));
            }
        }
    }

    /** Upserts all records and logs the run in a single transaction. */
    public void save(List<SuburbRecord> records, String source, int rejected, Instant startedAt)
            throws SQLException {
        boolean previousAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);
        try (PreparedStatement upsert = connection.prepareStatement(UPSERT_SQL);
             PreparedStatement run = connection.prepareStatement(RUN_SQL)) {
            for (SuburbRecord r : records) {
                upsert.setString(1, r.code());
                upsert.setString(2, r.name());
                upsert.setString(3, r.state());
                upsert.setDouble(4, r.latitude());
                upsert.setDouble(5, r.longitude());
                upsert.setInt(6, r.population());
                upsert.setDouble(7, r.medianAge());
                upsert.setInt(8, r.medianWeeklyRent());
                upsert.setInt(9, r.walkScore());
                upsert.setDouble(10, r.greenSpacePct());
                upsert.setInt(11, r.ptStops());
                upsert.setInt(12, r.referenceYear());
                upsert.addBatch();
            }
            upsert.executeBatch();

            run.setString(1, source);
            run.setInt(2, records.size());
            run.setInt(3, rejected);
            run.setTimestamp(4, Timestamp.from(startedAt));
            run.executeUpdate();

            connection.commit();
        } catch (SQLException e) {
            connection.rollback();
            throw e;
        } finally {
            connection.setAutoCommit(previousAutoCommit);
        }
    }
}
