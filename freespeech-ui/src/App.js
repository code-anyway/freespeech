import logo from './freespeechlogo.svg';
import './App.css';

import Navbar from './Navbar.js';
import Hero from './components/Hero.js';
import Features from './components/Features.js';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        {/* <Navbar /> */}
        <Hero />
        <Features />
      </header>
    </div>
  );
}

export default App;
