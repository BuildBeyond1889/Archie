// A console program in Java with a menu and safe number input. Run: java Main.java
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

public class Main {
    static Scanner in = new Scanner(System.in);

    static Integer readInt(String prompt) {
        while (true) {
            System.out.print(prompt);
            if (!in.hasNextLine()) return null;
            String s = in.nextLine().trim();
            try {
                return Integer.parseInt(s);
            } catch (NumberFormatException e) {
                System.out.println("Please type a whole number.");
            }
        }
    }

    public static void main(String[] args) {
        List<String> notes = new ArrayList<>();
        System.out.println("== My Java program ==");
        while (true) {
            System.out.println("\n1) Add a note\n2) List notes\n0) Quit");
            Integer c = readInt("Choose: ");
            if (c == null || c == 0) break;
            if (c == 1) {
                System.out.print("Note: ");
                if (in.hasNextLine()) notes.add(in.nextLine());
            } else if (c == 2) {
                for (int i = 0; i < notes.size(); i++) System.out.println((i + 1) + ". " + notes.get(i));
                if (notes.isEmpty()) System.out.println("(no notes yet)");
            } else {
                System.out.println("No option " + c + ".");
            }
        }
        System.out.println("Bye.");
    }
}
