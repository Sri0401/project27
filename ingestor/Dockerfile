# Build stage: compile, test and package a single runnable jar.
FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q package

# Runtime stage: small JRE image running as a non-root user.
FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S app && adduser -S app -G app
USER app
COPY --from=build /src/target/ingestor.jar /app/ingestor.jar
ENTRYPOINT ["java", "-jar", "/app/ingestor.jar"]
