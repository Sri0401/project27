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

    private static final String DELETE_SQL = "DELETE FROM suburb_indicators";

    private static final String INSERT_SQL = """
            INSERT INTO suburb_indicators (code, name, state, latitude, longitude, area_sqkm, population,
                median_age, median_weekly_rent, median_household_income, green_space_pct, pt_stops,
                road_crashes_per_year, reference_year, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
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

    /**
     * Replaces the whole table with these records and logs the run, in a single transaction.
     * Readers keep seeing the previous snapshot until the commit, and a failure leaves it untouched.
     */
    public void save(List<SuburbRecord> records, String source, int rejected, Instant startedAt)
            throws SQLException {
        boolean previousAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);
        try (Statement delete = connection.createStatement();
             PreparedStatement insert = connection.prepareStatement(INSERT_SQL);
             PreparedStatement run = connection.prepareStatement(RUN_SQL)) {
            delete.executeUpdate(DELETE_SQL);
            for (SuburbRecord r : records) {
                insert.setString(1, r.code());
                insert.setString(2, r.name());
                insert.setString(3, r.state());
                insert.setDouble(4, r.latitude());
                insert.setDouble(5, r.longitude());
                insert.setDouble(6, r.areaSqkm());
                insert.setInt(7, r.population());
                insert.setDouble(8, r.medianAge());
                insert.setInt(9, r.medianWeeklyRent());
                insert.setInt(10, r.medianHouseholdIncome());
                insert.setDouble(11, r.greenSpacePct());
                insert.setInt(12, r.ptStops());
                insert.setDouble(13, r.roadCrashesPerYear());
                insert.setInt(14, r.referenceYear());
                insert.addBatch();
            }
            insert.executeBatch();

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
