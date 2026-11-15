import type { ReactNode } from 'react';
import { ScrollView } from 'react-native';
import { maxWidth, space, useTheme } from '../theme';

/** Scrollable screen container with theme background and centered content (max ~880 px on web). */
export default function Screen({ children, center }: { children: ReactNode; center?: boolean }) {
  const { colors } = useTheme();
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{
        padding: space.xl,
        paddingBottom: space.xxl * 2,
        width: '100%',
        maxWidth,
        alignSelf: 'center',
        flexGrow: 1,
        justifyContent: center ? 'center' : 'flex-start',
      }}
    >
      {children}
    </ScrollView>
  );
}
