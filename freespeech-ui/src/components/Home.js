import logo from '../freespeechlogo.svg';

export default function Home() {
  return (
    <div className="Home">
        <img src={logo} className="Home-logo" alt="logo" />
        <h1>Home Page</h1>
        <p>
        </p>
        <a
          className="Home-link"
          href="https://freespeechnow.ai/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Welcome to FreeSpeech
        </a>
    </div>
  )
}
