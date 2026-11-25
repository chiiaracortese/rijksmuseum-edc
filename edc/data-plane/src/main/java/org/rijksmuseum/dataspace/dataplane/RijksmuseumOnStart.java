package org.rijksmuseum.dataspace.dataplane;

import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.eclipse.dataplane.Dataplane;
import org.eclipse.dataplane.domain.DataAddress;
import org.eclipse.dataplane.domain.Result;
import org.eclipse.dataplane.domain.dataflow.DataFlow;
import org.eclipse.dataplane.logic.OnStart;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.nio.file.Files;
import java.nio.file.Path;

public final class RijksmuseumOnStart extends HttpServlet implements OnStart {

    private static final long serialVersionUID = 1L;

    private static final String PUBLIC_URL =
            "http://data-plane:8181/public/rijksmuseum/";

    private static final SecureRandom RANDOM = new SecureRandom();

    private final ConcurrentHashMap<String, Grant> grants =
            new ConcurrentHashMap<>();


    private volatile Dataplane dataplane;

    private final RijksmuseumAssetRegistry assetRegistry;

    public RijksmuseumOnStart(
            RijksmuseumAssetRegistry assetRegistry
    ) {
        this.assetRegistry = Objects.requireNonNull(assetRegistry);
    }

    private record Grant(String token, Instant expiresAt) {
    }

    public void attach(Dataplane dataplane) {
        this.dataplane = Objects.requireNonNull(dataplane);
    }

    @Override
    public Result<DataFlow> action(DataFlow flow) {

        if (flow.getType() != DataFlow.Type.PROVIDER
                || !flow.isPull()
                || !assetRegistry.contains(flow.getDatasetId())
                || !"provider".equals(flow.getParticipantId())
                || !"provider".equals(flow.getControlplaneId())
                || flow.getCounterPartyId() == null
                || flow.getCounterPartyId().isBlank()
                || flow.getAgreementId() == null
                || flow.getAgreementId().isBlank()
                || flow.getDataAddress() != null) {

            return Result.failure(
                    new IllegalArgumentException(
                            "Flusso Rijksmuseum PULL non valido"
                    )
            );
        }

        byte[] randomBytes = new byte[32];
        RANDOM.nextBytes(randomBytes);

        String token = Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(randomBytes);

        grants.put(
                flow.getId(),
                new Grant(token, Instant.now().plus(Duration.ofMinutes(30)))
        );

        DataAddress address = new DataAddress(
                "https://w3id.org/idsa/v4.1/HTTP",
                PUBLIC_URL + flow.getId(),
                List.of(
                        new DataAddress.EndpointProperty(
                                null, "authorization", token
                        ),
                        new DataAddress.EndpointProperty(
                                null, "authType", "bearer"
                        )
                )
        );

        flow.setDataAddress(address);

        return Result.success(flow);
    }

    public Result<DataFlow> revoke(DataFlow flow) {
        grants.remove(flow.getId());
        return Result.success(flow);
    }

    @Override
    protected void doGet(
            HttpServletRequest request,
            HttpServletResponse response
    ) throws IOException {

        response.setHeader("Cache-Control", "no-store");

        String path = request.getPathInfo();

        if (path == null
                || !path.startsWith("/")
                || path.length() < 2
                || path.substring(1).contains("/")) {

            response.sendError(404);
            return;
        }

        String flowId = path.substring(1);

        Grant grant = grants.get(flowId);

        String authorization = request.getHeader("Authorization");

        if (grant == null
                || authorization == null
                || !authorization.startsWith("Bearer ")
                || Instant.now().isAfter(grant.expiresAt())) {

            response.sendError(401);
            return;
        }

        String suppliedToken = authorization.substring(7);

        boolean tokenMatches = MessageDigest.isEqual(
                suppliedToken.getBytes(StandardCharsets.UTF_8),
                grant.token().getBytes(StandardCharsets.UTF_8)
        );

        if (!tokenMatches) {
            response.sendError(401);
            return;
        }

        Dataplane activeDataplane = dataplane;

        if (activeDataplane == null) {
            response.sendError(503);
            return;
        }

        Result<DataFlow> lookup = activeDataplane.getById(flowId);

        if (lookup.failed()) {
            response.sendError(403);
            return;
        }

        DataFlow flow = lookup.getContent();

        if (!flow.isStarted()
                || !assetRegistry.contains(flow.getDatasetId())) {

            response.sendError(403);
            return;
        }

        // Il file rimane privato al container Provider: nessun Nginx aggiuntivo.
        Path file = assetRegistry.fileFor(flow.getDatasetId());
        if (!Files.isRegularFile(file) || Files.isSymbolicLink(file)) {
            response.sendError(404);
            return;
        }
        response.setStatus(200);
        response.setContentType("application/json");
        try (var input = Files.newInputStream(file)) {
            input.transferTo(response.getOutputStream());
        }

    }
}
