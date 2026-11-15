import { Redirect } from 'expo-router';
import { useMode } from '../src/mode';
export default function Index() { const { onboarded } = useMode(); return <Redirect href={onboarded ? '/feed' : '/onboarding'} />; }
