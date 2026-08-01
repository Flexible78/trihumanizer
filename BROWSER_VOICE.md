# Dictation and speech in Chromium / Edge / Yandex Browser

## Quick dictation check

1. Run `START_TRANSLATOR.bat`.
2. Open the app in Edge, Chrome, or Yandex Browser.
3. Press **Start dictation** and allow the microphone for `http://127.0.0.1:...`.
4. Speak slowly: "Привет. Как твои дела? Проверяю непрерывную диктовку".
5. Pause for 2–3 seconds, then keep speaking.
6. The app keeps the recognized text and automatically starts a new browser session.
7. Finish with the **Stop** button, not with a pause.

## Quick speech check

1. Enter Russian text in the input field.
2. Press **Read** next to the source text.
3. Open **Speech settings** to change the voice or rate.
4. Long texts are read in short chunks automatically.

## If the microphone is blocked

- Click the lock/permissions icon left of the address bar.
- Allow the microphone for `127.0.0.1`.
- Make sure the microphone is not busy in Telegram, Zoom, or another app.
- Reload the tab after changing the permission.

## If reading is silent

- Open speech settings and pick a specific Russian/English/Hebrew voice.
- Check the tab volume and the Windows mixer.
- Make sure Windows has a voice installed for the needed language.
- Press **Stop**, then **Read** again.
- Compare behavior in Edge or Chrome if a specific Yandex build does not
  return system voices.

Recognition and speech use the browser's Web Speech API. No separate voice API
key is required. Voice availability and the network recognition service are
determined by the browser and Windows.
