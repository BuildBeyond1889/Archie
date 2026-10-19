// A text adventure game loop in C++: rooms, moving between them, items. g++ main.cpp -o game
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

struct Room {
    std::string name, text;
    std::map<std::string, std::string> exits;   // direction -> room id
    std::vector<std::string> items;
};

int main() {
    std::map<std::string, Room> world = {
        {"gate", {"Farm gate", "A wooden gate. A path runs north.", {{"north", "yard"}}, {}}},
        {"yard", {"Yard", "Chickens everywhere. The barn is east, the gate south.", {{"south", "gate"}, {"east", "barn"}}, {"bucket"}}},
        {"barn", {"Barn", "Dark and dusty. The yard is west.", {{"west", "yard"}}, {"lamp"}}},
    };
    std::string here = "gate";
    std::vector<std::string> bag;
    std::cout << "Type: look, go <direction>, take <thing>, bag, quit\n";
    std::string line;
    while (true) {
        Room& r = world[here];
        std::cout << "\n[" << r.name << "] " << r.text << "\n";
        for (auto& it : r.items) std::cout << "You see a " << it << ".\n";
        std::cout << "> " << std::flush;
        if (!std::getline(std::cin, line)) break;
        std::istringstream in(line);
        std::string verb, what;
        in >> verb >> what;
        if (verb == "quit") break;
        if (verb == "go") {
            auto e = r.exits.find(what);
            if (e != r.exits.end()) here = e->second;
            else std::cout << "You can't go " << (what.empty() ? "nowhere" : what) << ".\n";
        } else if (verb == "take") {
            bool found = false;
            for (size_t i = 0; i < r.items.size(); i++)
                if (r.items[i] == what) { bag.push_back(what); r.items.erase(r.items.begin() + i); found = true; break; }
            std::cout << (found ? "Taken.\n" : "That isn't here.\n");
        } else if (verb == "bag") {
            std::cout << "You carry:";
            for (auto& b : bag) std::cout << " " << b;
            std::cout << (bag.empty() ? " nothing\n" : "\n");
        } else if (verb != "look") {
            std::cout << "I don't understand \"" << verb << "\".\n";
        }
    }
    std::cout << "Thanks for playing.\n";
    return 0;
}
