import google_auth_oauthlib.flow

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


# Reference resources:
# - https://github.com/tokland/youtube-upload/blob/master/youtube_upload/auth/__init__.py  # noqa: 501
# - https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps#python  # noqa: 501
# - https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html  # noqa: 501
def authorize(secret_file, credentials_file):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        secret_file,
        scopes=YOUTUBE_SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    )

    # Generate URL for request to Google's OAuth 2.0 server.
    # Use kwargs to set optional request parameters.
    authorization_url, _ = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission.
        # recommended for web server apps.
        access_type="offline",
        prompt="consent",
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes="true",
    )

    print(f"Please go to this URL: {authorization_url}")

    # The user will get an authorization code. This code is used to get the
    # access token.
    code = input("Enter the authorization code: ")
    flow.fetch_token(code=code)

    with open(credentials_file, "w") as fd:
        fd.write(flow.credentials.to_json())
