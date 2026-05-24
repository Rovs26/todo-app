import { onUnmounted, ref } from 'vue'
import { aiApi } from '~/utils/api'

/**
 * Voice-to-text helper.
 *
 * Strategy:
 *   1. If MediaRecorder is available, record a short clip and POST it to the
 *      backend's Whisper endpoint. This is the high-quality path (works in
 *      any browser, including Firefox).
 *   2. If the backend reports Whisper is unavailable (no API key) or the
 *      upload fails, fall back to the browser's Web Speech API.
 *   3. If neither path is available, ``supported`` is ``false``.
 */
export function useVoiceInput() {
  const transcript = ref('')
  const listening = ref(false)
  const transcribing = ref(false)
  const error = ref<string | null>(null)
  const source = ref<'whisper' | 'web-speech' | null>(null)

  const SpeechRecognition =
    typeof window !== 'undefined'
      ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      : null

  const hasWebSpeech = !!SpeechRecognition
  const hasMediaRecorder =
    typeof window !== 'undefined' && typeof window.MediaRecorder !== 'undefined'

  const supported = hasWebSpeech || hasMediaRecorder

  let recognition: any = null
  let mediaRecorder: MediaRecorder | null = null
  let mediaStream: MediaStream | null = null
  let chunks: Blob[] = []
  let onResultCb: ((text: string) => void) | null = null

  async function start(onResult?: (text: string) => void) {
    if (!supported) {
      error.value = 'Voice input is not supported in this browser'
      return
    }
    error.value = null
    transcript.value = ''
    onResultCb = onResult ?? null

    if (hasMediaRecorder) {
      try {
        await startWhisperRecording()
        return
      } catch (err: any) {
        error.value = err?.message ?? null
        // Fall through to Web Speech if available
      }
    }
    if (hasWebSpeech) {
      startWebSpeech()
    }
  }

  function stop() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      try {
        mediaRecorder.stop()
      } catch {
        /* ignore */
      }
    }
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        /* ignore */
      }
    }
  }

  async function startWhisperRecording() {
    chunks = []
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = pickSupportedMime()
    mediaRecorder = mimeType
      ? new MediaRecorder(mediaStream, { mimeType })
      : new MediaRecorder(mediaStream)

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunks.push(event.data)
    }
    mediaRecorder.onstart = () => {
      listening.value = true
    }
    mediaRecorder.onerror = (event: any) => {
      error.value = event?.error?.message || 'Recording error'
      listening.value = false
      releaseStream()
    }
    mediaRecorder.onstop = async () => {
      listening.value = false
      releaseStream()
      if (chunks.length === 0) return

      transcribing.value = true
      try {
        const blob = new Blob(chunks, {
          type: mediaRecorder?.mimeType || 'audio/webm',
        })
        const ext = (blob.type.split('/')[1] || 'webm').split(';')[0]
        const result = await aiApi.transcribe(blob, `recording.${ext}`)
        if (result.text) {
          transcript.value = result.text
          source.value = 'whisper'
          onResultCb?.(result.text)
        } else {
          // Whisper not configured server-side — fall back to Web Speech
          if (hasWebSpeech) {
            startWebSpeech()
          } else {
            error.value = 'Voice transcription is not available'
          }
        }
      } catch (err: any) {
        error.value = err?.message ?? 'Could not transcribe audio'
      } finally {
        transcribing.value = false
      }
    }

    mediaRecorder.start()
  }

  function startWebSpeech() {
    recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.continuous = false

    recognition.onstart = () => {
      listening.value = true
      source.value = 'web-speech'
    }
    recognition.onresult = (event: any) => {
      let text = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        text += event.results[i][0].transcript
      }
      transcript.value = text.trim()
      if (event.results[event.results.length - 1].isFinal && onResultCb) {
        onResultCb(transcript.value)
      }
    }
    recognition.onerror = (event: any) => {
      error.value = event?.error || 'Voice recognition error'
      listening.value = false
    }
    recognition.onend = () => {
      listening.value = false
    }
    try {
      recognition.start()
    } catch (err: any) {
      error.value = err?.message || 'Could not start voice input'
      listening.value = false
    }
  }

  function pickSupportedMime(): string | null {
    if (typeof MediaRecorder === 'undefined') return null
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ]
    for (const c of candidates) {
      if ((MediaRecorder as any).isTypeSupported?.(c)) return c
    }
    return null
  }

  function releaseStream() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop())
      mediaStream = null
    }
  }

  onUnmounted(() => {
    stop()
    releaseStream()
  })

  return {
    transcript,
    listening,
    transcribing,
    supported,
    error,
    source,
    start,
    stop,
  }
}
