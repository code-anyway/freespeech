import logo from './freespeechlogo.svg';

function Navbar() {
  return (
    <div className="Navbar">
      <img src={logo} className="Home-logo" alt="logo" />        
      
      <nav class="stroke">
        <ul>
          <li><a href="/">Home</a></li>
          <li><a href="/#about">About</a></li>
          <li><a href="/#transcribe">Transcribe</a></li>
          <li><a href="/#translate">Translate</a></li>
          <li><a href="/#dub">Dub/Voiceover</a></li>
        </ul>
      </nav>
    </div>
  );
}

export default Navbar;
