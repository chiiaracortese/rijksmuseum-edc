package org.rijksmuseum.dataspace.dataplane;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import java.util.regex.Pattern;

public final class RijksmuseumAssetRegistry {

    private static final String PREFIX = "asset.";

    private static final Pattern ASSET_ID = Pattern.compile(
            "[A-Za-z0-9][A-Za-z0-9._-]*"
    );

    private static final Pattern FILENAME = Pattern.compile(
            "[A-Za-z0-9][A-Za-z0-9._-]*\\.json"
    );

    private final Map<String, String> assets;

    public RijksmuseumAssetRegistry(Path configPath)
            throws IOException {

        if (!Files.isRegularFile(configPath)
                || Files.isSymbolicLink(configPath)) {
            throw new IOException(
                    "Registro Asset non disponibile"
            );
        }

        Properties properties = new Properties();

        try (var input = Files.newInputStream(configPath)) {
            properties.load(input);
        }

        Map<String, String> loaded = new HashMap<>();

        for (String key : properties.stringPropertyNames()) {

            if (!key.startsWith(PREFIX)) {
                throw new IllegalArgumentException(
                        "Chiave di configurazione non consentita"
                );
            }

            String assetId = key.substring(PREFIX.length());
            String filename = properties.getProperty(key);

            if (!ASSET_ID.matcher(assetId).matches()
                    || filename == null
                    || !FILENAME.matcher(filename).matches()
                    || filename.contains("..")) {

                throw new IllegalArgumentException(
                        "Associazione Asset non valida: " + assetId
                );
            }

            loaded.put(assetId, filename);
        }

        if (loaded.isEmpty()) {
            throw new IllegalArgumentException(
                    "Registro Asset vuoto"
            );
        }

        assets = Map.copyOf(loaded);
    }

    public boolean contains(String assetId) {
        return assetId != null && assets.containsKey(assetId);
    }

    public String filenameFor(String assetId) {

        String filename = assets.get(assetId);

        if (filename == null) {
            throw new IllegalArgumentException(
                    "Asset non autorizzato nel registro"
            );
        }

        return filename;
    }

    /** Percorso file locale, da un mount Docker in sola lettura. */
    public Path fileFor(String assetId) {
        return Path.of(System.getenv().getOrDefault(
                "RIJKSMUSEUM_DATA_DIR", "/data/rijksmuseum"
        )).resolve(filenameFor(assetId));
    }

    public int size() {
        return assets.size();
    }
}
