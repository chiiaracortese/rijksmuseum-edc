plugins {
    application
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.eclipse.dataplane-core:dataplane-sdk-core:1.2.1")
    implementation("org.eclipse.dataplane-core:dataplane-sdk-jakarta-ee:1.2.1")

    implementation("org.glassfish.jersey.inject:jersey-hk2:4.0.3")
    implementation("org.glassfish.jersey.containers:jersey-container-servlet:4.0.3")
    implementation("org.glassfish.jersey.media:jersey-media-json-jackson3:4.0.3")

    implementation("org.eclipse.jetty.ee10:jetty-ee10-servlet:12.1.13")
    implementation("org.eclipse.jetty:jetty-server:12.1.13")

    runtimeOnly("org.slf4j:slf4j-simple:2.0.20")
}

application {
    mainClass.set("org.rijksmuseum.dataspace.dataplane.RijksmuseumDataPlaneMain")
}
