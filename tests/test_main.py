from command_launcher.main import main

def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert "Hello, from command-launcher!" in captured.out
