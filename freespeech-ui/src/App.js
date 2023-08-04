import { useState } from 'react';
import logo from './freespeechlogo.svg';
import './App.css';

import Navbar from './Navbar.js';
import Hero from './components/Hero.js';
import Features from './components/Features.js';
import Login from './user/Login.js';

function App() {
  const [user, setUser] = useState(null)

  return (
    <div className="App">
      <header className="App-header">
        {/* <Navbar /> */}
        <Hero user={user} />
        <Features user={user} />
        <Login user={user} />
      </header>
    </div>
  );
}

export default App;
