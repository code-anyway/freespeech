import logo from './freespeechlogo.svg';

function Navbar() {
  return (
    <div className="Navbar">
        <a
          className="Home-link"
          href="https://freespeechnow.ai/"
        ></a>
        <a class="active" href="#home">Home</a>
        <a href="#news">News</a>
        <a href="#contact">Contact</a>
        <a href="#about">About</a>
    </div>
  );
}

export default Navbar;
