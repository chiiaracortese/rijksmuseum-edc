package org.rijksmuseum.dataspace.dataplane;

import java.net.URI;
import java.nio.file.Path;
import org.eclipse.dataplane.Dataplane;
import org.eclipse.dataplane.domain.Result;
import org.eclipse.dataplane.domain.dataflow.DataFlow;
import org.eclipse.dataplane.domain.registration.Oauth2ClientCredentialsAuthorization;
import org.eclipse.dataplane.port.DataPlaneSignalingApiController;
import org.eclipse.dataplane.port.DataPlaneRegistrationApiController;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.eclipse.jetty.ee10.servlet.ServletContextHandler;
import org.eclipse.jetty.ee10.servlet.ServletHolder;
import org.eclipse.jetty.ee10.servlet.Source;
import org.glassfish.jersey.server.ResourceConfig;
import org.glassfish.jersey.servlet.ServletContainer;

/** Un solo processo Java per entrambi i ruoli DPS del laboratorio locale. */
public final class RijksmuseumDataPlaneMain {
    public static void main(String[] args) throws Exception {
        var registro = new RijksmuseumAssetRegistry(Path.of("/config/edc-assets.properties"));
        var esposizione = new RijksmuseumOnStart(registro);
        var ricezione = new RijksmuseumConsumerOnStarted(registro);

        var dataplane = Dataplane.newInstance()
                .id("rijksmuseum-shared-dataplane")
                .endpoint(URI.create("http://data-plane:8181/api/v1/dataflows"))
                .registerAuthorization(new Oauth2ClientCredentialsAuthorization(
                        "http://auth-service:8080/oauth2/jwks"))
                .profile("HttpData-PULL")
                // Ruolo Provider: concede accesso al dataset con token temporaneo.
                .onStart(esposizione)
                .onSuspend(esposizione::revoke)
                .onTerminate(esposizione::revoke)
                .onCompleted(esposizione::revoke)
                // Ruolo Consumer: autorizzazione e ricezione nel medesimo processo.
                .onPrepare(flow -> {
                    if (flow.getType() != DataFlow.Type.CONSUMER || !flow.isPull()
                            || !"consumer".equals(flow.getControlplaneId())
                            || !registro.contains(flow.getDatasetId())
                            || flow.getAgreementId() == null || flow.getAgreementId().isBlank()) {
                        return Result.failure(new IllegalArgumentException("Preparazione Consumer non valida"));
                    }
                    return Result.success(flow);
                })
                .onStarted(ricezione)
                .build();
        esposizione.attach(dataplane);

        var api = new ResourceConfig();
        api.register(new DataPlaneSignalingApiController(dataplane));
        api.register(new DataPlaneRegistrationApiController(dataplane));
        var server = new Server();
        var connector = new ServerConnector(server);
        connector.setHost("0.0.0.0");
        connector.setPort(8181);
        server.setConnectors(new org.eclipse.jetty.server.Connector[]{connector});
        var context = new ServletContextHandler(ServletContextHandler.NO_SESSIONS);
        context.setContextPath("/");
        var signalingServlet = new ServletHolder(Source.EMBEDDED);
        signalingServlet.setServlet(new ServletContainer(api));
        context.getServletHandler().addServletWithMapping(signalingServlet, "/api/*");
        var publicServlet = new ServletHolder(Source.EMBEDDED);
        publicServlet.setServlet(esposizione);
        context.getServletHandler().addServletWithMapping(publicServlet, "/public/rijksmuseum/*");
        server.setHandler(context);
        server.start();
        System.out.println("EDC laboratorio: UN solo Data Plane Java sulla porta 8181");
        server.join();
    }
}
