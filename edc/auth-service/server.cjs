'use strict';

const http = require('node:http');
const fs = require('node:fs');
const crypto = require('node:crypto');

const privateKey = crypto.createPrivateKey(
  fs.readFileSync('/keys/jwt-private.pem')
);
const publicKey = crypto.createPublicKey(
  fs.readFileSync('/keys/jwt-public.pem')
);

const kid = 'rijksmuseum-rsa-1';
const jwk = publicKey.export({ format: 'jwk' });

const jwks = {
  keys: [{
    kty: jwk.kty,
    n: jwk.n,
    e: jwk.e,
    kid,
    use: 'sig',
    alg: 'RS256'
  }]
};

const clients = new Map([
  ['provider', process.env.PROVIDER_OAUTH_CLIENT_SECRET],
  [
    'rijksmuseum-provider-dataplane',
    process.env.DATA_PLANE_OAUTH_CLIENT_SECRET
  ],
  ['consumer', process.env.CONSUMER_OAUTH_CLIENT_SECRET],
  [
    'rijksmuseum-consumer-dataplane',
    process.env.CONSUMER_DATA_PLANE_OAUTH_CLIENT_SECRET
  ]
]);

for (const secret of clients.values()) {
  if (!secret || secret.length < 32) {
    throw new Error('Credenziali OAuth2 mancanti o insufficienti');
  }
}

function respond(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-store',
    'Pragma': 'no-cache'
  });
  res.end(body);
}

function equalSecret(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') {
    return false;
  }
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

function issueToken(subject) {
  const now = Math.floor(Date.now() / 1000);

  const header = {
    alg: 'RS256',
    typ: 'JWT',
    kid
  };

  const payload = {
    iss: 'http://auth-service:8080',
    sub: subject,
    aud: 'rijksmuseum-data-plane-signaling',
    iat: now,
    nbf: now,
    exp: now + 300,
    jti: crypto.randomUUID()
  };

  const encode = value =>
    Buffer.from(JSON.stringify(value)).toString('base64url');

  const unsigned = encode(header) + '.' + encode(payload);

  const signature = crypto.sign(
    'RSA-SHA256',
    Buffer.from(unsigned),
    privateKey
  ).toString('base64url');

  return unsigned + '.' + signature;
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/oauth2/jwks') {
    return respond(res, 200, jwks);
  }

  if (req.method === 'POST' && req.url === '/oauth2/token') {
    if (!(req.headers['content-type'] || '')
        .startsWith('application/x-www-form-urlencoded')) {
      return respond(res, 415, {
        error: 'unsupported_media_type'
      });
    }

    let body = '';
    let tooLarge = false;

    req.on('data', chunk => {
      body += chunk;
      if (body.length > 8192) {
        tooLarge = true;
      }
    });

    req.on('end', () => {
      if (tooLarge) {
        return respond(res, 413, { error: 'invalid_request' });
      }

      const form = new URLSearchParams(body);

      if (form.get('grant_type') !== 'client_credentials') {
        return respond(res, 400, {
          error: 'unsupported_grant_type'
        });
      }

      let id = form.get('client_id');
      let secret = form.get('client_secret');

      const auth = req.headers.authorization || '';
      if (auth.startsWith('Basic ')) {
        const decoded = Buffer.from(
          auth.slice(6), 'base64'
        ).toString('utf8');
        const separator = decoded.indexOf(':');
        if (separator >= 0) {
          id = decoded.slice(0, separator);
          secret = decoded.slice(separator + 1);
        }
      }

      if (!clients.has(id) ||
          !equalSecret(clients.get(id), secret)) {
        return respond(res, 401, {
          error: 'invalid_client'
        });
      }

      return respond(res, 200, {
        access_token: issueToken(id),
        token_type: 'Bearer',
        expires_in: 300
      });
    });

    return;
  }

  return respond(res, 404, { error: 'not_found' });
});

server.listen(8080, '0.0.0.0', () => {
  console.log('Rijksmuseum auth-service avviato sulla porta 8080');
});
