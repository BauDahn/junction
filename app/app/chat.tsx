import { StyleSheet, Text, View } from 'react-native';
export default function ChatScreen() {
  return (
    <View style={s.container}>
      <Text style={s.eyebrow}>JUNCTION · STARTUP INTELLIGENCE</Text>
      <Text style={s.title}>Chat</Text>
      <Text style={s.placeholder}>Próximamente</Text>
      <Text style={s.hint}>Aquí podrás contarle al asistente sobre tu startup.</Text>
    </View>
  );
}
const s = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#0b1020' },
  eyebrow: {
    color: '#a78bfa',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
    marginBottom: 10,
  },
  title: { color: '#f8fafc', fontSize: 32, fontWeight: '800' },
  placeholder: { color: '#c4b5fd', fontSize: 22, fontWeight: '700', marginTop: 24 },
  hint: { color: '#9aa6bf', fontSize: 15, marginTop: 8 },
});
