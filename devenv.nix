{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.pipenv
    pkgs.python310Packages.pip
  ];

  languages.python.enable = true;
  languages.python.package = pkgs.python310;
}

   
