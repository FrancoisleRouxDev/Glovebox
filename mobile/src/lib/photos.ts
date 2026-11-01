/**
 * Photo helpers: shrink photos before upload, and keep copies of saved ones.
 */
import { Directory, File, Paths } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

/** Same limit as the backend: longest side at most 1024px. */
const MAX_SIDE_PX = 1024;
const JPEG_QUALITY = 0.8;

/**
 * Resize so the longest side is <= 1024px and re-encode as JPEG.
 * Cuts upload size from several MB to roughly 100-300 KB, and turns HEIC
 * (iPhone) or PNG images into JPEG. Returns the URI of a new temporary file.
 */
export async function resizeForUpload(uri: string, width: number, height: number): Promise<string> {
  const context = ImageManipulator.manipulate(uri);
  // Pickers can report 0x0 when the size is unknown. Then we resize by width
  // as a best effort.
  const longest = Math.max(width, height);
  if (longest === 0) {
    context.resize({ width: MAX_SIDE_PX, height: null });
  } else if (longest > MAX_SIDE_PX) {
    // Only set one side: the other is computed to keep the aspect ratio.
    context.resize(width >= height ? { width: MAX_SIDE_PX, height: null } : { width: null, height: MAX_SIDE_PX });
  }
  const image = await context.renderAsync();
  const result = await image.saveAsync({ format: SaveFormat.JPEG, compress: JPEG_QUALITY });
  return result.uri;
}

/**
 * Copy a temporary (cache) photo into the app's document directory so it
 * survives the OS clearing the cache. Returns the new file:// URI.
 */
export async function savePhotoPermanently(tempUri: string): Promise<string> {
  const dir = new Directory(Paths.document, 'photos');
  dir.create({ idempotent: true, intermediates: true });
  const destination = new File(dir, `car-${Date.now()}.jpg`);
  await new File(tempUri).copy(destination);
  return destination.uri;
}

/** Delete a saved photo. Never throws: a missing file is not worth crashing over. */
export function deletePhoto(uri: string): void {
  try {
    const file = new File(uri);
    if (file.exists) file.delete();
  } catch (err) {
    console.warn('Could not delete photo', uri, err);
  }
}
