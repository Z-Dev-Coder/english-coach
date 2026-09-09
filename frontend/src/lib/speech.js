/**
 * Browser speech: text-to-speech for listening, speech-to-text for speaking.
 *
 * Both are native Web APIs, so they cost nothing and need no server round trip.
 * Support is uneven, though — Chrome and Edge have both, Firefox has synthesis
 * only, and iOS Safari is inconsistent — so every function here reports
 * availability rather than assuming it, and callers must degrade gracefully.
 */

const synth = typeof window !== "undefined" ? window.speechSynthesis : null;

const SpeechRecognition =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

export const canSpeak = Boolean(synth);
export const canListen = Boolean(SpeechRecognition);

/** Voices load asynchronously in some browsers, and are empty on first call. */
export function loadVoices() {
  return new Promise((resolve) => {
    if (!synth) return resolve([]);
    const voices = synth.getVoices();
    if (voices.length) return resolve(voices);
    const onChange = () => {
      synth.removeEventListener("voiceschanged", onChange);
      resolve(synth.getVoices());
    };
    synth.addEventListener("voiceschanged", onChange);
    // Some browsers never fire the event; do not hang the UI waiting for it.
    setTimeout(() => resolve(synth.getVoices()), 1000);
  });
}

/** Prefer a natural-sounding English voice, falling back to any English one. */
export async function pickVoice(preferredLang = "en-US") {
  const voices = await loadVoices();
  if (!voices.length) return null;
  const english = voices.filter((voice) => voice.lang?.startsWith("en"));
  const pool = english.length ? english : voices;
  return (
    pool.find((voice) => voice.lang === preferredLang && !voice.localService) ||
    pool.find((voice) => voice.lang === preferredLang) ||
    pool[0]
  );
}

/**
 * Speak a sentence.
 *
 * `rate` below 1 is genuinely useful for listening practice: hearing the same
 * sentence slowly and then at natural speed is the point of the exercise.
 */
export function speak(text, { rate = 1, voice = null, onEnd, onError } = {}) {
  if (!synth || !text) {
    onError?.(new Error("Speech synthesis is not available in this browser."));
    return () => {};
  }

  // Chrome queues utterances and will happily talk over itself otherwise.
  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = rate;
  utterance.lang = voice?.lang || "en-US";
  if (voice) utterance.voice = voice;
  utterance.onend = () => onEnd?.();
  utterance.onerror = (event) => {
    // "interrupted" and "canceled" fire whenever we deliberately stop playback;
    // they are not failures worth surfacing to the learner.
    if (event.error === "interrupted" || event.error === "canceled") return;
    onError?.(new Error(event.error || "Playback failed."));
  };
  synth.speak(utterance);

  return () => synth.cancel();
}

export function stopSpeaking() {
  synth?.cancel();
}

/**
 * Listen to the microphone and resolve with a transcript.
 *
 * Returns { promise, stop }. The caller stops it explicitly rather than relying
 * on silence detection, which is unreliable for learners who pause mid-sentence
 * while searching for a word.
 */
export function listen({ lang = "en-US", interim } = {}) {
  if (!SpeechRecognition) {
    return {
      promise: Promise.reject(
        new Error(
          "Speech recognition is not supported in this browser. Chrome or Edge will work.",
        ),
      ),
      stop: () => {},
    };
  }

  const recognition = new SpeechRecognition();
  recognition.lang = lang;
  recognition.continuous = true;
  recognition.interimResults = Boolean(interim);
  recognition.maxAlternatives = 1;

  let finalTranscript = "";
  let settled = false;

  const promise = new Promise((resolve, reject) => {
    recognition.onresult = (event) => {
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) finalTranscript += `${result[0].transcript} `;
        else interimText += result[0].transcript;
      }
      interim?.(`${finalTranscript}${interimText}`.trim());
    };

    recognition.onerror = (event) => {
      if (settled) return;
      settled = true;
      const messages = {
        "not-allowed": "Microphone access was blocked. Allow it in your browser settings.",
        "service-not-allowed": "Microphone access was blocked by your browser.",
        "no-speech": "I didn't hear anything. Try again a little louder.",
        network: "Speech recognition needs a network connection.",
        aborted: "",
      };
      const message = messages[event.error] ?? `Speech recognition failed (${event.error}).`;
      // An abort is our own stop() call landing after the result; resolve with
      // whatever was captured instead of reporting an error.
      if (!message) resolve(finalTranscript.trim());
      else reject(new Error(message));
    };

    recognition.onend = () => {
      if (settled) return;
      settled = true;
      resolve(finalTranscript.trim());
    };
  });

  try {
    recognition.start();
  } catch {
    // start() throws if called twice; the existing session is what we want.
  }

  return { promise, stop: () => recognition.stop() };
}
