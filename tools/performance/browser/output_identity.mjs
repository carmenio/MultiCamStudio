import { createHash } from 'node:crypto'

// Hash a populated operator-shell signature so direct viewer pages cannot be
// mistaken for evidence that the application shell rendered equivalently.
export function hashOperatorShellSignature(serializedSignature) {
  let signature
  try {
    signature = JSON.parse(String(serializedSignature))
  } catch (error) {
    throw new Error('operator shell identity was not valid JSON', { cause: error })
  }

  if (
    !Array.isArray(signature.navigation)
    || signature.navigation.length === 0
    || !Array.isArray(signature.sessions)
    || signature.sessions.length === 0
    || typeof signature.activeMain !== 'string'
    || signature.activeMain.length === 0
  ) {
    throw new Error('operator shell identity requires populated navigation, sessions, and main content')
  }

  return createHash('sha256').update(String(serializedSignature)).digest('hex')
}
