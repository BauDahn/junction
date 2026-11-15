import { useMemo, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { requestFavoritesReport } from '../api/favoritesReport';
import { getAuthToken } from '../api/auth';
import { useMode } from '../mode';
import { getSessionId } from '../session';
import { font, radius, space, useTheme } from '../theme';

export function FavoritesReportButton() {
  const { colors } = useTheme();
  const { favoriteInvestorIds, mode, user } = useMode();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  if (favoriteInvestorIds.length === 0) return null;

  const downloadReport = async () => {
    if (loading) return;
    setError('');
    setNotice('');
    if (Platform.OS !== 'web') {
      setNotice('Saving the PDF is available in the web app for now.');
      return;
    }

    setLoading(true);
    try {
      const sessionId = user?.session_id ?? await getSessionId();
      let authToken: string | null = null;
      try {
        authToken = await getAuthToken();
      } catch {
        authToken = null;
      }
      const { blob, notIncluded } = await requestFavoritesReport(favoriteInvestorIds, { sessionId, authToken, mode });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'cala-match-favorites.pdf';
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`Report downloaded.${notIncluded.length ? ` ${notIncluded.length} favorite${notIncluded.length === 1 ? '' : 's'} were not in Cala and were left out.` : ''}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Cannot reach the server.');
    } finally {
      setLoading(false);
    }
  };

  return <View style={styles.container}>
    <Pressable accessibilityRole="button" accessibilityLabel="Download favorites report (PDF)" accessibilityState={{ disabled: loading }} disabled={loading} onPress={() => void downloadReport()} style={styles.button}>
      {loading ? <ActivityIndicator color={colors.accentText} /> : null}
      <Text style={styles.buttonText}>{loading ? 'Building your report…' : error ? 'Try again' : 'Download favorites report (PDF)'}</Text>
    </Pressable>
    <Text style={styles.muted}>Takes up to a minute. Data from Cala, action plan by Gemini.</Text>
    {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
    {notice ? <Text accessibilityLiveRegion="polite" style={styles.muted}>{notice}</Text> : null}
  </View>;
}

const makeStyles = (c: ReturnType<typeof useTheme>['colors']) => StyleSheet.create({
  container: { gap: space.sm, paddingTop: space.md },
  button: { minHeight: 44, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: space.sm, backgroundColor: c.accent, borderRadius: radius.md, paddingHorizontal: space.lg, paddingVertical: space.sm },
  buttonText: { color: c.accentText, fontSize: font.small, fontWeight: '600' },
  muted: { color: c.textMuted, fontSize: font.small },
  error: { color: c.danger, fontSize: font.small },
});
