import logo from './freespeechlogo.svg';
import './App.css';

import Navbar from './Navbar.js';
import Home from './components/Home.js';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <Navbar />
        <Home />
      </header>
    </div>
  );
}

export default App;
