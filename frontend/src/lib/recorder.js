import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Records the microphone so the learner can hear themselves back.
 *
 * The app already used SpeechRecognition, which returns a *transcript* and
 * nothing else. That is enough to score whether the right words were said and
 * useless for the thing shadowing is actually for: hearing that your rhythm is
 * flat, or that you put the beat on the wrong word. Recognition will happily
 * report a perfect transcript of a sentence delivered like a shopping list.
 *
 * So this runs MediaRecorder alongside it. Same microphone permission, no
 * upload, no cost -- the audio becomes a blob URL in the page and is revoked
 * when it is replaced or the component goes away.
 *
 * Nothing here is required for practice to work. Every failure path leaves
 * `supported` or `error` set and the caller carries on without playback,
 * because a browser that will not record is not a reason to stop practising.
 */

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? "";
}

export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [url, setUrl] = useState(null);
  const [error, setError] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const urlRef = useRef(null);

  const supported =
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia;

  const replaceUrl = useCallback((next) => {
    // Blob URLs are held by the document until revoked, so a session of
    // twenty attempts would otherwise pin twenty recordings in memory.
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = next;
    setUrl(next);
  }, []);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (!supported || recording) return;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
        chunksRef.current = [];
        // A zero-length blob means nothing was captured -- a muted mic, or a
        // stop that arrived before the first chunk. Offering a silent player
        // would look like the recording failed to play.
        replaceUrl(blob.size ? URL.createObjectURL(blob) : null);
        stopTracks();
        setRecording(false);
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (err) {
      // Denied permission, no microphone, or an insecure origin. All the same
      // to the caller: there will be no playback.
      setError(err);
      stopTracks();
      setRecording(false);
    }
  }, [supported, recording, replaceUrl, stopTracks]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    else setRecording(false);
  }, []);

  const clear = useCallback(() => replaceUrl(null), [replaceUrl]);

  useEffect(
    () => () => {
      // Leaving the page mid-recording must release the microphone, or the
      // browser keeps showing the recording indicator.
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      stopTracks();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [stopTracks],
  );

  return { supported, recording, url, error, start, stop, clear };
}
