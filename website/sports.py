from flask import Blueprint, render_template

sports = Blueprint("sports", __name__)


@sports.route("/test")
def test():
    return "<h1>Test</h1>"


@sports.route("/Basketball")
def Basketball():
    return render_template("Basketball.html")


@sports.route("/Hockey")
def Hockey():
    return render_template("Hockey.html")


@sports.route("/Lacrosse")
def Lacrosse():
    return render_template("Lacrosse.html")


@sports.route("/Football")
def Football():
    return render_template("Football.html")


@sports.route("/Volleyball")
def Volleyball():
    return render_template("Volleyball.html")


@sports.route("/Wrestling")
def Wrestling():
    return render_template("Wrestling.html")


@sports.route("/Soccer")
def Soccer():
    return render_template("Soccer.html")


@sports.route("/Softball")
def Softball():
    return render_template("Softball.html")


@sports.route("/Baseball")
def Baseball():
    return render_template("Baseball.html")


@sports.route("/Gymnastics")
def Gymnastics():
    return render_template("copyPasta.html")


@sports.route("/Debug")
def Debug():
    return render_template("Debug.html")
