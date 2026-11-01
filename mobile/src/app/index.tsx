/**
 * Scan screen: take a photo with the camera or pick one from the gallery,
 * shrink it, then open the Result screen, which does the upload.
 */
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { router, useIsFocused } from 'expo-router';
import { useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { BackendStatus } from '@/components/BackendStatus';
import { Button } from '@/components/ui';
import { resizeForUpload } from '@/lib/photos';
import { colors, spacing } from '@/theme';

export default function ScanScreen() {
  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Only one camera preview can be active at a time, so we unmount the camera
  // whenever this screen isn't visible (e.g. while Result is on top).
  const isFocused = useIsFocused();

  /** Leaving this screen unmounts the camera, so it must report "ready" again on return. */
  function leaveScreen(go: () => void) {
    setCameraReady(false);
    go();
  }

  /** Shared by camera and gallery: resize, then hand off to the Result screen. */
  async function handlePhoto(uri: string, width: number, height: number) {
    setBusy(true);
    setError(null);
    try {
      const resizedUri = await resizeForUpload(uri, width, height);
      leaveScreen(() => router.push({ pathname: '/result', params: { uri: resizedUri } }));
    } catch (err) {
      console.warn('Photo processing failed', err);
      setError('Could not process that photo. Please try another one.');
    } finally {
      setBusy(false);
    }
  }

  async function takePhoto() {
    if (!cameraRef.current || !cameraReady || busy) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.9 });
      await handlePhoto(photo.uri, photo.width, photo.height);
    } catch (err) {
      console.warn('Camera capture failed', err);
      setError('Could not take a photo. Please try again.');
    }
  }

  async function pickFromGallery() {
    if (busy) return;
    // No permission needed to open the system photo picker.
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 1 });
    if (result.canceled) return;
    const asset = result.assets[0];
    await handlePhoto(asset.uri, asset.width, asset.height);
  }

  return (
    <View style={styles.container}>
      <BackendStatus />

      <View style={styles.preview}>
        {!permission ? (
          <ActivityIndicator color={colors.primaryText} />
        ) : !permission.granted ? (
          <View style={styles.permission}>
            <Text style={styles.permissionText}>Camera access lets you snap cars directly.</Text>
            <Button title="Allow camera" onPress={requestPermission} />
          </View>
        ) : isFocused ? (
          <CameraView
            ref={cameraRef}
            style={StyleSheet.absoluteFill}
            facing="back"
            onCameraReady={() => setCameraReady(true)}
          />
        ) : null}
        {busy && (
          <View style={styles.busyOverlay}>
            <ActivityIndicator size="large" color={colors.primaryText} />
            <Text style={styles.busyText}>Preparing photo…</Text>
          </View>
        )}
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.controls}>
        <Pressable onPress={pickFromGallery} style={styles.sideButton} disabled={busy}>
          <Text style={styles.sideButtonText}>Gallery</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Take photo"
          onPress={takePhoto}
          disabled={!cameraReady || busy}
          style={({ pressed }) => [
            styles.shutter,
            (!cameraReady || busy) && { opacity: 0.4 },
            pressed && { transform: [{ scale: 0.95 }] },
          ]}
        />
        <Pressable onPress={() => leaveScreen(() => router.push('/collection'))} style={styles.sideButton}>
          <Text style={styles.sideButtonText}>Collection</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  preview: { flex: 1, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center' },
  permission: { padding: spacing.lg, alignItems: 'center' },
  permissionText: { color: colors.primaryText, textAlign: 'center', fontSize: 16 },
  busyOverlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(0,0,0,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  busyText: { color: colors.primaryText, fontSize: 16 },
  error: { color: colors.danger, textAlign: 'center', padding: spacing.sm },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    paddingBottom: spacing.lg,
  },
  sideButton: { width: 90, paddingVertical: spacing.sm, alignItems: 'center' },
  sideButtonText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
  shutter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primary,
    borderWidth: 4,
    borderColor: colors.surface,
  },
});
