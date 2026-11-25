package org.rijksmuseum.dataspace.dataplane;

import org.eclipse.dataplane.domain.DataAddress;
import org.eclipse.dataplane.domain.Result;
import org.eclipse.dataplane.domain.dataflow.DataFlow;
import org.eclipse.dataplane.logic.OnStarted;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;

public final class RijksmuseumConsumerOnStarted implements OnStarted {

    private static final long DEFAULT_MAX_BYTES =
            1024L * 1024 * 1024;

    private final RijksmuseumAssetRegistry assetRegistry;
    private final long maxBytes;

    public RijksmuseumConsumerOnStarted(
            RijksmuseumAssetRegistry assetRegistry
    ) {
        this.assetRegistry =
                java.util.Objects.requireNonNull(assetRegistry);

        String configured = System.getenv().getOrDefault(
                "DATA_PLANE_MAX_DOWNLOAD_BYTES",
                Long.toString(DEFAULT_MAX_BYTES)
        );

        try {
            maxBytes = Long.parseLong(configured);
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(
                    "Limite dimensionale Consumer non valido",
                    exception
            );
        }

        if (maxBytes <= 0) {
            throw new IllegalArgumentException(
                    "Il limite dimensionale deve essere positivo"
            );
        }
    }

    private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    @Override
    public Result<DataFlow> action(DataFlow flow) {

        try {
            if (flow.getType() != DataFlow.Type.CONSUMER
                    || !flow.isPull()
                    || !assetRegistry.contains(flow.getDatasetId())) {
                throw new IllegalArgumentException(
                        "Flusso Consumer PULL non valido"
                );
            }

            DataAddress address = flow.getDataAddress();

            if (address == null || address.endpoint() == null) {
                throw new IllegalArgumentException(
                        "Indirizzo del trasferimento mancante"
                );
            }

            URI endpoint = URI.create(address.endpoint());

            if (!"http".equals(endpoint.getScheme())
                    || !"data-plane".equals(endpoint.getHost())
                    || endpoint.getPort() != 8181
                    || endpoint.getRawPath() == null
                    || !endpoint.getRawPath().startsWith(
                            "/public/rijksmuseum/")
                    || endpoint.getRawQuery() != null
                    || endpoint.getRawFragment() != null
                    || endpoint.getRawUserInfo() != null) {
                throw new IllegalArgumentException(
                        "Endpoint Provider non consentito"
                );
            }

            String token = null;

            if (address.endpointProperties() != null) {
                for (var property : address.endpointProperties()) {
                    if ("authorization".equals(property.name())) {
                        token = property.value();
                    }
                }
            }

            if (token == null || token.isBlank()) {
                throw new IllegalArgumentException(
                        "Token del trasferimento mancante"
                );
            }

            HttpRequest request = HttpRequest.newBuilder(endpoint)
                    .timeout(Duration.ofSeconds(60))
                    .header("Authorization", "Bearer " + token)
                    .GET()
                    .build();

            Path folder = Path.of(
                    System.getenv().getOrDefault(
                            "DATA_PLANE_RECEIVED_DIR", "/received"
                    )
            );

            Files.createDirectories(folder);

            // Directory distinta per ogni DataFlow.
            String flowId = flow.getId();

            if (flowId == null || flowId.isBlank()) {
                throw new IllegalArgumentException(
                        "Identificativo DataFlow mancante"
                );
            }

            // L'hash evita di utilizzare direttamente
            // caratteri dell'ID all'interno del percorso.
            String directoryId = HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(
                            flowId.getBytes(
                                    java.nio.charset.StandardCharsets.UTF_8
                            )
                    )
            );

            folder = folder.resolve("workflow").resolve(directoryId);

            Files.createDirectories(folder.getParent());

            System.out.println("Rijksmuseum DataFlow ID: " + flowId);
            System.out.println(
                    "Rijksmuseum Agreement ID: " + flow.getAgreementId()
            );

            Path output = folder.resolve(
                        assetRegistry.filenameFor(flow.getDatasetId())
                );
            // Il file temporaneo resta fuori dalla directory
            // definitiva finché il download non è riuscito.
            Path temporary = Files.createTempFile(
                    folder.getParent(), "rijksmuseum-", ".part"
            );

            try {
                HttpResponse<java.io.InputStream> response =
                        client.send(
                                request,
                                HttpResponse.BodyHandlers.ofInputStream()
                        );

                try (var input = response.body()) {

                    if (response.statusCode() != 200) {
                        throw new IOException(
                                "Download rifiutato dal Provider: HTTP "
                                + response.statusCode()
                        );
                    }

                    long total = 0;

                    MessageDigest digest =
                            MessageDigest.getInstance("SHA-256");

                    try (var stream = Files.newOutputStream(temporary)) {
                        byte[] buffer = new byte[8192];
                        int count;

                        while ((count = input.read(buffer)) != -1) {
                            total += count;

                            if (total > maxBytes) {
                                throw new IOException(
                                        "Dimensione massima superata"
                                );
                            }

                            stream.write(buffer, 0, count);
                            digest.update(buffer, 0, count);
                        }
                    }

                    if (total == 0) {
                        throw new IOException("Dataset ricevuto vuoto");
                    }

                    // Pubblicazione finale senza sovrascrittura.
                    // La directory viene creata solo dopo il download.
                    Files.createDirectory(folder);

                    try {
                        Files.move(temporary, output);
                    } catch (IOException moveError) {
                        // Rimuove soltanto la directory vuota
                        // creata da questa esecuzione.
                        try {
                            Files.deleteIfExists(folder);
                        } catch (IOException cleanupError) {
                            // Se non è vuota, la preserva.
                            moveError.addSuppressed(cleanupError);
                        }

                        throw moveError;
                    }

                    byte[] hash = digest.digest();

                    // Ricevuta tecnica relativa al file appena ricevuto.
                    // Non contiene token o altre credenziali.
                    java.util.Properties receipt =
                            new java.util.Properties();

                    String agreementId = flow.getAgreementId();

                    if (agreementId == null || agreementId.isBlank()) {
                        throw new IOException(
                                "Agreement ID mancante nella ricevuta"
                        );
                    }

                    receipt.setProperty("dataflow_id", flowId);
                    receipt.setProperty("agreement_id", agreementId);
                    receipt.setProperty(
                            "asset_id", flow.getDatasetId()
                    );
                    receipt.setProperty(
                            "filename", output.getFileName().toString()
                    );
                    receipt.setProperty(
                            "received_bytes", Long.toString(total)
                    );
                    receipt.setProperty(
                            "received_sha256",
                            HexFormat.of().formatHex(hash)
                    );
                    receipt.setProperty(
                            "received_at_utc",
                            java.time.Instant.now().toString()
                    );

                    Path receiptPath = folder.resolve(
                            "transfer-receipt.properties"
                    );

                    Path receiptTemporary = Files.createTempFile(
                            folder, "receipt-", ".part"
                    );

                    try {
                        try (var receiptStream =
                                Files.newOutputStream(receiptTemporary)) {
                            receipt.store(
                                    receiptStream,
                                    "Rijksmuseum DataFlow receipt"
                            );
                        }

                        Files.move(receiptTemporary, receiptPath);
                    } finally {
                        Files.deleteIfExists(receiptTemporary);
                    }

                    System.out.println(
                            "Rijksmuseum PULL ricevuto: "
                            + total + " byte"
                    );

                    System.out.println(
                            "SHA-256: " + HexFormat.of().formatHex(hash)
                    );
                }

            } finally {
                Files.deleteIfExists(temporary);
            }

            return Result.success(flow);

        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();

            return Result.failure(
                    new IOException("Trasferimento interrotto")
            );

        } catch (Exception exception) {
            return Result.failure(exception);
        }
    }
}
