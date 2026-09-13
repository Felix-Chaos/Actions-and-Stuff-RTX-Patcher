// German. Same key shape as en.js; anything missing falls back to English.
export default {
  common: {
    cancel: 'Abbrechen',
    ok: 'OK',
  },
  modal: {
    notificationTitle: 'Benachrichtigung',
    confirmTitle: 'Bestätigen',
    telemetryConsent: {
      title: 'Hilf uns, seltene RTX-Probleme zu diagnostizieren',
      intro: 'Bestimmte Renderfehler treten nur bei bestimmten Kombinationen aus GPU und Treiber auf. Mit deiner Zustimmung kann der Patcher eine <b>pseudonyme Hardware-Übersicht</b> übermitteln',
      whatsTheDifference: 'was ist der Unterschied?',
      introAfter: ', um solche Fälle zu erkennen. Die Übermittlung ist freiwillig und wird einmalig beim ersten Start abgefragt. Danach wird deine Hardware bei jedem Start geprüft, und eine neue Übermittlung erfolgt nur, wenn sich das Ergebnis vom vorherigen unterscheidet, zum Beispiel nach einem Wechsel von GPU, Treiber oder BetterRTX-Preset:',
      notCollected: '<b>Nicht erfasst:</b> dein Name, deine Dateien oder Seriennummern. Jede Übermittlung wird durch eine zufällig erzeugte <b>Installations-ID</b> und einen Einweg-Hash deines Rechners gekennzeichnet. Beide dienen ausschließlich dazu, wiederholte Übermittlungen derselben Installation zu erkennen, damit sie nach einer Neuinstallation nicht doppelt gezählt wird. Weil diese Kennungen dauerhaft sind und Übermittlungen über die Zeit verknüpfen, spricht man von pseudonym statt anonym. Beide lassen sich jederzeit in den Einstellungen unter „Delete My Data" löschen, was auch den zugehörigen Datensatz auf dem Server entfernt. Jede Übermittlung wird zusätzlich lokal als <code>last_hardware_ping.json</code> gespeichert, damit du sie einsehen kannst. Hochgeladene Bug-Report-Logs werden nach 30 Tagen gelöscht.',
      point1: 'GPU-Modell, Treiberversion & VRAM',
      point2: 'CPU-Modell, RAM-Größe, Windows-Build',
      point3: 'Minecraft-Edition (Store / Launcher) & Patcher-Version',
      decline: 'Ablehnen',
      accept: 'Berichterstattung aktivieren',
    },
  },
  sidebar: {
    language: 'Sprache',
  },
  tabAppSettings: {
    language: {
      label: 'Sprache',
      hint: 'Log- und Konsolenausgabe bleibt auf Englisch.',
    },
  },
};
