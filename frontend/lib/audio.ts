export function playAudioB64(b64: string) {
  const audio = new Audio(`data:audio/mp3;base64,${b64}`);
  audio.play();
}

export function b64ToBlob(b64: string, mimeType = "audio/mp3"): Blob {
  const byteChars = atob(b64);
  const byteNums = new Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteNums[i] = byteChars.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNums);
  return new Blob([byteArray], { type: mimeType });
}
