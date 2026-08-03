// Format per-camera media state so a failed seek identifies the stalled source.
export function formatRecordingSeekDiagnostic(states) {
  return states.map((state) => {
    const source = state.source || 'unknown'
    const readyState = Number.isFinite(state.readyState) ? state.readyState : 'unknown'
    const currentTime = Number.isFinite(state.currentTime) ? state.currentTime : 'unknown'
    return `camera[${state.index}] source="${source}" readyState=${readyState} currentTime=${currentTime} outcome=${state.outcome}`
  }).join('; ')
}
