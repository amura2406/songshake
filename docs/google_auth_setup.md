# Setting up Google Cloud Credentials for Song Shake

To use the "Single Button Login" or secure Google Login, you need to create your own Google Cloud project and credentials. This allows the app to authenticate as *you* (or your project) to access YouTube Music.

## Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top-left (next to the Google Cloud logo).
3. Click **New Project**.
4. Give it a name like "Song Shake" and click **Create**.
5. Select the project you just created.

## Step 2: Configure OAuth Consent Screen
1. In the left sidebar, go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (unless you have a Google Workspace organization, then Internal is fine).
3. Click **Create**.
4. **App Information**:
   - **App name**: Song Shake
   - **User support email**: Select your email.
   - **Developer contact information**: Enter your email.
5. Click **Save and Continue**.
6. **Scopes**:
   - Click **Add or Remove Scopes**.
   - Search for `youtube` and select `../auth/youtube` (Manage your YouTube account).
   - If acceptable, you can also select `../auth/youtube.force-ssl` or just `../auth/youtube` is usually enough for `ytmusicapi`.
   - Click **Update** and then **Save and Continue**.
7. **Test Users**:
   - Click **+ Add Users**.
   - Enter **your own email address** (the one you want to login with).
   - *Important: Without this, you will get a 403 Access Denied error.*
   - Click **Save and Continue**.

## Step 3: Create OAuth Client ID
1. In the left sidebar, go to **APIs & Services** > **Credentials**.
2. Click **+ Create Credentials** > **OAuth client ID**.
3. **Application type**: Select **TVs and Limited Input devices**.
   - *Why?* Song Shake uses the "Device Code Flow" to avoid complex redirect setups on your local machine.
4. **Name**: "Song Shake Client".
5. Click **Create**.

## Step 4: Get Credentials
1. You will see a popup with **Client ID** and **Client Secret**.
2. Copy these values.
3. Paste them into your `.env` file in the `song-shake` directory:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

## Step 5: Run Song Shake
1. Start the frontend: `npm run dev`
2. Start the backend: `python src/song_shake/api.py`
3. Go to the Login page. It should now show "Login with Google" automatically!
