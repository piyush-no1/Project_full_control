
import React from 'react';
import { AppProvider, useApp } from './state/AppContext';
import { Screen } from './types';
import IntroScreen from './screens/IntroScreen';
import GestureDashboard from './screens/GestureDashboard';
import LoginScreen from './screens/LoginScreen';
import ControlDashboard from './screens/ControlDashboard';
import { LoadingOverlay } from './components/UI';

const AppContent: React.FC = () => {
  const { currentScreen, isLoading } = useApp();

  const renderScreen = () => {
    switch (currentScreen) {
      case Screen.INTRO:
        return <IntroScreen />;
      case Screen.GESTURE_DASHBOARD:
        return <GestureDashboard />;
      case Screen.LOGIN:
        return <LoginScreen />;
      case Screen.CONTROL_DASHBOARD:
        return <ControlDashboard />;
      default:
        return <IntroScreen />;
    }
  };

  return (
    <div className="relative w-full h-screen">
      <LoadingOverlay active={isLoading} />
      {renderScreen()}
    </div>
  );
};

const App: React.FC = () => {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
};

export default App;
