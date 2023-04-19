{ pkgs, ... }:

{
  packages = [
    pkgs.python310Packages.pip
  ];

  languages.python.enable = true;
  languages.python.venv.enable = true;
  languages.python.package = pkgs.python310;
}

   
