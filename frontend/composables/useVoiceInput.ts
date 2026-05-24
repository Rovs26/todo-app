import { ref, onUnmounted } from 'vue'

/**
 * Wraps the browser's Web Speech API for one-shot voice-to-text.
 *
 * Free, no API key, works in Chromium-family browsers and Safari.
 * Falls back gracefully (``supported = false``) on browsers without it.
 */
export function useVoiceInput() {
  const transcript = ref('')
  const listening = ref(false)
  const error = ref<string | null>(null)

  const SpeechRecognition =
    typeof window !== 'undefined'
      ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      : null

  const supported = !!SpeechRecognition

  let recognition: any = null

  function start(onResult?: (text: string) => void) {
    if (!supported) {
      error.value = 'Voice input is not supported in this browser'
      return
    }
    error.value = null
    transcript.value = ''
    recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.continuous = false

    recognition.onstart = () => {
      listening.value = true
    }
    recognition.onresult = (event: any) => {
      let text = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        text += event.results[i][0].transcript
      }
      transcript.value = text.trim()
      if (event.results[event.results.length - 1].isFinal && onResult) {
        onResult(transcript.value)
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

  function stop() {
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        /* ignore */
      }
    }
  }

  onUnmounted(stop)

  return { transcript, listening, supported, error, start, stop }
}
