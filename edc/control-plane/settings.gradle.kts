pluginManagement {
    repositories { mavenCentral(); gradlePluginPortal() }
}

dependencyResolutionManagement {
    repositories { mavenCentral(); mavenLocal() }
}

rootProject.name = "rijksmuseum-control-plane"
include(":provider", ":consumer", ":policy-functions")
