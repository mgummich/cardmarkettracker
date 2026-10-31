from cmtracker.providers.oauth import build_auth_header


def test_signature_matches_reference_vector():
    # Referenzbeispiel aus der Twitter-OAuth-1.0a-Doku ("Creating a signature"),
    # gegengeprüft mit oauthlib
    header = build_auth_header(
        "POST",
        "https://api.twitter.com/1.1/statuses/update.json",
        app_token="xvz1evFS4wEEPTGEFPHBog",
        app_secret="kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
        access_token="370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
        access_token_secret="LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
        params={
            "include_entities": "true",
            "status": "Hello Ladies + Gentlemen, a signed OAuth request!",
        },
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg",
        timestamp="1318622958",
    )
    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in header
    assert header.startswith('OAuth realm="https://api.twitter.com/1.1/statuses/update.json"')
