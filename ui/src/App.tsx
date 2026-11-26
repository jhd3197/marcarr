import { createBrowserRouter, RouterProvider } from 'react-router';
import { AppFrame, Shell } from './components/Shell';
import { ToastProvider } from './lib/toast';
import Library from './pages/Library';
import TitlePage from './pages/Title';
import ScenePage from './pages/Scene';
import Review from './pages/Review';
import Search from './pages/Search';
import Tags from './pages/Tags';
import ActivityPage from './pages/Activity';
import SettingsPage from './pages/Settings';
import ApiPage from './pages/Api';
import PersonPage from './pages/Person';
import PlacePage from './pages/Place';
import FirstRun from './pages/FirstRun';

// A show and a movie share /titles/:id (the page switches on type); a scene is
// /videos/:video/scenes/:n; a place id has slashes (hogwarts/great-hall).
const router = createBrowserRouter([
  { path: '/setup', element: <FirstRun /> },
  {
    element: <Shell />,
    children: [
      { path: '/', element: <Library /> },
      { path: '/titles/:id', element: <TitlePage /> },
      { path: '/videos/:video/scenes/:n', element: <ScenePage /> },
      { path: '/review', element: <Review /> },
      { path: '/search', element: <Search /> },
      { path: '/tags', element: <Tags /> },
      { path: '/activity', element: <ActivityPage /> },
      { path: '/settings', element: <SettingsPage /> },
      { path: '/api', element: <ApiPage /> },
      { path: '/people/:id', element: <PersonPage /> },
      { path: '/places/*', element: <PlacePage /> },
    ],
  },
]);

export default function App() {
  return (
    <AppFrame>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AppFrame>
  );
}
