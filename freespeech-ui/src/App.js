import logo from './freespeechlogo.svg';
import './App.css';

import Navbar from './Navbar.js';
import Hero from './components/Hero.js';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        {/* <Navbar /> */}
        <Hero />
      </header>
    </div>
  );
}

export default App;
